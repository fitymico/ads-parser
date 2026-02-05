#!/usr/bin/env python3
"""
Параллельный конвейер обработки объявлений

Архитектура:
  [Парсер URL] -> Queue1 -> [Скачивание данных] -> Queue2 -> [Скачивание+Обработка изображений]
       |                           |                                       |
    1 процесс                 N процессов                              M процессов
                                   |
                                   v
                          [Shared: ads_list, image_map]
                                   |
                                   v
                            [SQL Generator]
"""

import argparse
import hashlib
import io
import os
import re
import sys
import time
from dataclasses import dataclass
from multiprocessing import Process, Queue, Manager, Event, cpu_count
from queue import Empty
from typing import Optional, Dict, List
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CITIES
from models import Ad
from parser.client import HttpClient
from parser.listing import ListingParser
from parser.detail import DetailParser
from mapper.cities import get_city_region


# ============================================================
# Конфигурация
# ============================================================

@dataclass
class PipelineConfig:
    """Конфигурация конвейера"""
    # Workers
    data_workers: int = 2
    image_workers: int = 2

    # Rate limiting
    request_delay: float = 0.15
    max_retries: int = 3

    # Обработка изображений
    # Превью: лёгкое сжатие, водяной знак остаётся
    preview_quality: int = 90
    preview_max_size: int = 1600
    # Остальные: обрезка низа + сильное сжатие
    compress_quality: int = 75
    compress_max_size: int = 1200
    crop_bottom_pixels: int = 100  # Обрезка низа (водяной знак ~80px + отступ)
    max_photos_other: int = 3

    # Лимиты
    max_ads: int = 0  # 0 = без лимита

    # SQL
    sql_user_id: int = 4173

    # Пути
    images_dir: str = "./images"
    sql_file: str = "./export.sql"


POISON_PILL = "STOP"


# ============================================================
# Worker 1: Парсер URL
# ============================================================

def url_parser_worker(
    regions_to_parse: dict,
    url_queue: Queue,
    stats: dict,
    max_pages: int = None,
    skip_top: bool = False,
    request_delay: float = 0.15,
    max_ads: int = 0,
):
    """Собирает URL объявлений"""
    client = HttpClient()
    listing_parser = ListingParser(client)
    count = 0

    try:
        for region, cities in regions_to_parse.items():
            for city in cities:
                print(f"[URLs] {city}...")

                if not skip_top:
                    pages = listing_parser.get_total_pages(city, "gallery")
                    if max_pages:
                        pages = min(pages, max_pages)
                    for page in range(1, pages + 1):
                        for url, _ in listing_parser.get_listing_urls(city, "gallery", page):
                            url_queue.put((url, region, True))
                            count += 1
                            if max_ads and count >= max_ads:
                                break
                        if max_ads and count >= max_ads:
                            break
                        time.sleep(request_delay)
                    if max_ads and count >= max_ads:
                        break

                if max_ads and count >= max_ads:
                    break

                pages = listing_parser.get_total_pages(city, "list")
                if max_pages:
                    pages = min(pages, max_pages)
                for page in range(1, pages + 1):
                    for url, _ in listing_parser.get_listing_urls(city, "list", page):
                        url_queue.put((url, region, False))
                        count += 1
                        if max_ads and count >= max_ads:
                            break
                    if max_ads and count >= max_ads:
                        break
                    time.sleep(request_delay)

            if max_ads and count >= max_ads:
                break

        stats['urls_found'] = count
    finally:
        client.close()
        url_queue.put(POISON_PILL)
        print(f"[URLs] Готово: {count} URL")


# ============================================================
# Worker 2: Скачивание данных + изображений + обработка
# ============================================================

def data_worker(
    worker_id: int,
    url_queue: Queue,
    ads_list: list,
    image_map: dict,
    stats: dict,
    done_event: Event,
    config: PipelineConfig,
):
    """Скачивает данные объявления и его изображения"""
    import requests
    from PIL import Image

    client = HttpClient()
    detail_parser = DetailParser(client)

    # Создаём папки для превью и остальных
    preview_dir = os.path.join(config.images_dir, "preview")
    others_dir = os.path.join(config.images_dir, "images")
    os.makedirs(preview_dir, exist_ok=True)
    os.makedirs(others_dir, exist_ok=True)
    print(f"[Worker {worker_id}] Превью → preview/, Остальные → images/")

    processed_ads = 0
    processed_images = 0

    def crop_bottom(img, pixels=100):
        """Обрезка низа изображения"""
        w, h = img.size
        return img.crop((0, 0, w, h - pixels))

    def compress_image(img, max_size, quality):
        """Сжатие изображения"""
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
        return img, quality

    def process_image(url, is_preview):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()

            img = Image.open(io.BytesIO(resp.content))
            if img.mode != 'RGB':
                img = img.convert('RGB')

            file_hash = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:13]
            filename = f"{file_hash}.webp"

            if is_preview:
                # Превью: лёгкое сжатие, без обрезки (водяной знак остаётся)
                img, quality = compress_image(img, config.preview_max_size, config.preview_quality)
                filepath = os.path.join(preview_dir, filename)
            else:
                # Остальные: обрезка низа + сильное сжатие
                img = crop_bottom(img, config.crop_bottom_pixels)
                img, quality = compress_image(img, config.compress_max_size, config.compress_quality)
                filepath = os.path.join(others_dir, filename)

            buf = io.BytesIO()
            img.save(buf, format='WEBP', quality=quality)
            with open(filepath, 'wb') as f:
                f.write(buf.getvalue())

            return filename
        except Exception as e:
            return None

    try:
        while not done_event.is_set():
            try:
                task = url_queue.get(timeout=2)
            except Empty:
                continue

            if task == POISON_PILL:
                url_queue.put(POISON_PILL)
                break

            url, region, is_top = task

            # Парсим объявление
            ad = None
            for _ in range(config.max_retries):
                try:
                    ad = detail_parser.parse(url)
                    break
                except:
                    time.sleep(0.5)

            if not ad:
                continue

            if not ad.region:
                ad.region = region
            ad.is_top = is_top

            # Ограничиваем фото
            from export.unisite_export import map_categories
            from export.sql_export import get_category_id, limit_photos

            cat1, cat2 = map_categories(ad.category, ad.subcategory)
            category_id = get_category_id(cat1, cat2)
            photos = limit_photos(ad.photos or [], category_id, config.max_photos_other)

            # Скачиваем и обрабатываем изображения
            local_photos = []
            for idx, photo_url in enumerate(photos):
                if photo_url and photo_url.startswith('http'):
                    filename = process_image(photo_url, idx == 0)
                    if filename:
                        local_photos.append(filename)
                        image_map[photo_url] = filename
                        processed_images += 1
                    time.sleep(config.request_delay)

            # Сохраняем объявление с локальными путями
            ad.photos = local_photos
            ads_list.append({
                'ad': ad.__dict__,
                'category_id': category_id,
            })

            processed_ads += 1
            print(f"[W{worker_id}] #{processed_ads}: {ad.id} ({len(local_photos)} фото)")

            time.sleep(config.request_delay)

    finally:
        client.close()
        stats[f'worker_{worker_id}_ads'] = processed_ads
        stats[f'worker_{worker_id}_images'] = processed_images
        print(f"[Worker {worker_id}] Завершён: {processed_ads} ads, {processed_images} images")


# ============================================================
# SQL Generator
# ============================================================

def generate_sql(ads_list: list, config: PipelineConfig):
    """Генерирует SQL файл из собранных данных"""
    from export.sql_export import (
        escape_sql, escape_sql_or_empty, parse_price, generate_alias,
        format_datetime_today, clean_description, photos_to_json,
        get_city_id, get_region_id, COUNTRY_ID
    )
    from datetime import timedelta

    lines = [
        "-- SQL Export from ads-parser (parallel pipeline)",
        f"-- Generated: {datetime.now().isoformat()}",
        f"-- Total ads: {len(ads_list)}",
        "",
        "SET NAMES utf8mb4;",
        "",
    ]

    for item in ads_list:
        ad_dict = item['ad']
        category_id = item['category_id']

        # Восстанавливаем объект
        ad = Ad(**{k: v for k, v in ad_dict.items() if k in Ad.__dataclass_fields__})

        price = parse_price(ad.price)
        alias = generate_alias(ad.title, ad.id)
        datetime_add = format_datetime_today()
        period_end = datetime.now() + timedelta(days=30)
        period_publication = f"'{period_end.strftime('%Y-%m-%d %H:%M:%S')}'"
        cleaned_description = clean_description(ad.description, ad.phone, ad.seller_name)
        images_json = photos_to_json(ad.photos or [])
        city_id = get_city_id(ad.city) if ad.city else 0
        region_id = get_region_id(ad.region) if ad.region else 0
        vip = 1 if ad.is_top else 0
        import_id = f"dnr_red_{ad.id}"

        lat = float(ad.lat) if ad.lat else 0.0
        lng = float(ad.lng) if ad.lng else 0.0

        filter_tags_parts = [str(v) for v in (ad.params or {}).values()]
        filter_tags = escape_sql(';'.join(filter_tags_parts)) if filter_tags_parts else "''"

        search_parts = []
        if ad.title:
            search_parts.extend(ad.title.split()[:5])
        if ad.category:
            search_parts.append(ad.category)
        search_tags = escape_sql(';'.join(search_parts)[:255]) if search_parts else "''"

        sql = f"""INSERT INTO `nulled_ads` (
    `ads_title`, `ads_alias`, `ads_text`, `ads_id_cat`, `ads_datetime_add`, `ads_datetime_view`,
    `ads_id_user`, `ads_images`, `ads_price`, `ads_address`, `ads_latitude`, `ads_longitude`,
    `ads_metro_ids`, `ads_period_publication`, `ads_city_id`, `ads_status`, `ads_region_id`,
    `ads_country_id`, `ads_note`, `ads_count_display`, `ads_currency`, `ads_period_day`,
    `ads_update`, `ads_sorting`, `ads_auction`, `ads_auction_duration`, `ads_auction_price_sell`,
    `ads_auction_day`, `ads_area_ids`, `ads_id_import`, `ads_import_images`, `ads_video`,
    `ads_vip`, `ads_auto_renewal`, `ads_online_view`, `ads_price_old`, `ads_filter_tags`,
    `ads_price_free`, `ads_available`, `ads_available_unlimitedly`, `ads_booking`,
    `ads_price_measure`, `ads_price_from`, `ads_booking_additional_services`,
    `ads_booking_prepayment_percent`, `ads_booking_max_guests`, `ads_booking_min_days`,
    `ads_booking_max_days`, `ads_booking_available`, `ads_booking_available_unlimitedly`,
    `ads_electron_product_links`, `ads_electron_product_text`, `ads_delivery_status`,
    `ads_delivery_weight`, `ads_map_lat`, `ads_map_lon`, `ads_search_tags`, `ads_count_view`,
    `ads_condition_status`
) SELECT
    {escape_sql(ad.title)}, {escape_sql(alias)}, {escape_sql(cleaned_description)}, {category_id},
    {datetime_add}, NULL, {config.sql_user_id}, {images_json}, {price},
    {escape_sql_or_empty(ad.address)}, {escape_sql_or_empty(ad.lat)}, {escape_sql_or_empty(ad.lng)},
    '', {period_publication}, {city_id}, 1, {region_id}, {COUNTRY_ID}, '', 0,
    {escape_sql_or_empty(ad.currency)}, 30, NULL, 0, 0, NULL, 0, 1, '',
    {escape_sql(import_id)}, {images_json}, '', {vip}, 0, 0, 0, {filter_tags},
    {1 if price == 0 else 0}, 0, 0, 0, '', 0, '', 0, 0, 0, 0, 0, 0, NULL, NULL, 0, 0,
    {lat}, {lng}, {search_tags}, 0, 0
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `nulled_ads` WHERE `ads_id_import` = {escape_sql(import_id)});
"""
        lines.append(f"-- Ad: {ad.id}")
        lines.append(sql)

    lines.append(f"\n-- Export complete: {len(ads_list)} ads")

    with open(config.sql_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n[SQL] Сохранено: {config.sql_file} ({len(ads_list)} объявлений)")


# ============================================================
# Главный процесс
# ============================================================

def run_pipeline(regions_to_parse: dict, config: PipelineConfig, max_pages: int = None, skip_top: bool = False):
    """Запуск конвейера"""
    print("=" * 60)
    print("ПАРАЛЛЕЛЬНЫЙ КОНВЕЙЕР")
    print("=" * 60)
    print(f"Data workers: {config.data_workers}")
    print(f"Delay: {config.request_delay}s")
    print(f"Превью: quality={config.preview_quality}, max={config.preview_max_size}px → preview/")
    print(f"Остальные: crop={config.crop_bottom_pixels}px, quality={config.compress_quality}, max={config.compress_max_size}px → images/")
    if config.max_ads:
        print(f"Лимит: {config.max_ads} объявлений")
    print("=" * 60)

    manager = Manager()
    url_queue = Queue(maxsize=500)
    ads_list = manager.list()
    image_map = manager.dict()
    stats = manager.dict()
    done_event = Event()

    os.makedirs(config.images_dir, exist_ok=True)

    processes = []

    # URL Parser
    p = Process(target=url_parser_worker, args=(
        regions_to_parse, url_queue, stats, max_pages, skip_top, config.request_delay, config.max_ads
    ))
    p.start()
    processes.append(p)

    # Data workers
    time.sleep(1)  # Даём время URL парсеру начать
    for i in range(config.data_workers):
        p = Process(target=data_worker, args=(
            i, url_queue, ads_list, image_map, stats, done_event, config
        ))
        p.start()
        processes.append(p)

    # Ждём
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[Main] Прерывание...")
        done_event.set()
        for p in processes:
            p.terminate()
        return

    # Генерируем SQL
    print(f"\n[Main] Собрано {len(ads_list)} объявлений")
    if ads_list:
        generate_sql(list(ads_list), config)

    print("\n" + "=" * 60)
    print("ГОТОВО")
    print("=" * 60)
    print(f"Объявлений: {len(ads_list)}")
    print(f"Изображений: {len(image_map)}")
    print(f"SQL: {config.sql_file}")
    print(f"Images: {config.images_dir}/")
    print("=" * 60)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Параллельный конвейер")
    parser.add_argument("-r", "--region", choices=["ДНР", "ЛНР", "Запорожье", "Херсон"])
    parser.add_argument("-c", "--city")
    parser.add_argument("-p", "--max-pages", type=int)
    parser.add_argument("--skip-top", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--preview-quality", type=int, default=90, help="Качество превью (default: 90)")
    parser.add_argument("--quality", type=int, default=75, help="Качество остальных (default: 75)")
    parser.add_argument("--crop", type=int, default=100, help="Обрезка низа в px (default: 100)")
    parser.add_argument("--user-id", type=int, default=4173)
    parser.add_argument("-d", "--images-dir", default="./images")
    parser.add_argument("-o", "--output", default="./export.sql")

    args = parser.parse_args()

    config = PipelineConfig(
        data_workers=args.workers,
        request_delay=args.delay,
        preview_quality=args.preview_quality,
        compress_quality=args.quality,
        crop_bottom_pixels=args.crop,
        sql_user_id=args.user_id,
        images_dir=args.images_dir,
        sql_file=args.output,
    )

    if args.test:
        args.city = "donetsk"
        args.max_pages = 1
        config.max_ads = 10  # Лимит для теста

    if args.city:
        region = get_city_region(args.city)
        if not region:
            print(f"Неизвестный город: {args.city}")
            sys.exit(1)
        regions = {region: [args.city]}
    elif args.region:
        regions = {args.region: CITIES[args.region]}
    else:
        regions = CITIES

    run_pipeline(regions, config, args.max_pages, args.skip_top)


if __name__ == "__main__":
    main()
