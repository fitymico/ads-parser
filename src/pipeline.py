#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Параллельный конвейер обработки объявлений v2

Оптимизации:
  - Детерминированные имена файлов (md5 от URL)
  - Пропуск пустых категорий
  - Инкрементальная запись SQL (сразу в файл)
  - Resume: пропуск уже обработанных через журнал
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from multiprocessing import Process, Queue, Manager, Event, Lock
from queue import Empty
from typing import Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CITIES
from models import Ad
from parser.client import HttpClient
from parser.listing import ListingParser
from parser.detail import DetailParser
from mapper.cities import get_city_region
from parser.categories import get_categories, get_districts, get_known_districts


# ============================================================
# Конфигурация
# ============================================================

@dataclass
class PipelineConfig:
    """Конфигурация конвейера"""
    data_workers: int = 4

    # Rate limiting
    request_delay: float = 0.15
    max_retries: int = 3

    # Превью: лёгкое сжатие, водяной знак остаётся
    preview_quality: int = 90
    preview_max_size: int = 1600
    # Остальные: обрезка низа + сильное сжатие
    compress_quality: int = 75
    compress_max_size: int = 1200
    crop_bottom_pixels: int = 100
    max_photos_other: int = 3

    max_ads: int = 0  # 0 = без лимита
    sql_user_id: int = 4173

    images_dir: str = "./images"
    sql_file: str = "./export.sql"
    journal_file: str = "./processed_ids.txt"
    image_map_file: str = "./image_map.json"


POISON_PILL = "STOP"


# ============================================================
# Resume: загрузка состояния
# ============================================================

def load_processed_ids(journal_path: str) -> set:
    """Загрузить ID уже обработанных объявлений"""
    if not os.path.exists(journal_path):
        return set()
    ids = set()
    with open(journal_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(line)
    print(f"[Resume] Загружено {len(ids)} обработанных ID из {journal_path}")
    return ids


def load_image_map(path: str) -> dict:
    """Загрузить маппинг URL → filename"""
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        data = json.load(f)
    print(f"[Resume] Загружено {len(data)} записей image_map из {path}")
    return data


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
    use_deep_scan: bool = True,
    processed_ids: set = None,
):
    """
    Собирает URL объявлений

    Оптимизация: пропускает пустые категории (проверка родительской перед подкатегориями)
    """
    client = HttpClient()
    listing_parser = ListingParser(client)
    count = 0
    skipped = 0
    seen_urls = set()
    categories = get_categories()

    def should_stop():
        return max_ads and count >= max_ads

    def add_url(url, region, is_top):
        nonlocal count, skipped
        if url in seen_urls:
            return False
        seen_urls.add(url)
        # Пропускаем уже обработанные
        ad_id_match = re.search(r'-(\d{5,})\.html$', url)
        if processed_ids and ad_id_match and ad_id_match.group(1) in processed_ids:
            skipped += 1
            return False
        url_queue.put((url, region, is_top))
        count += 1
        return True

    try:
        for region, cities in regions_to_parse.items():
            if should_stop():
                break

            for city in cities:
                if should_stop():
                    break

                # Проверяем сколько страниц в городе БЕЗ фильтров
                city_total_pages = listing_parser.get_total_pages(city, "list")
                time.sleep(request_delay)

                # Если <50 страниц — простой скан, иначе deep scan (50 = лимит, могут быть ещё)
                city_needs_deep = use_deep_scan and city_total_pages >= 50

                if city_needs_deep:
                    print(f"[URLs] {city} ({city_total_pages} стр.) — deep scan...")
                else:
                    print(f"[URLs] {city} ({city_total_pages} стр.) — простой скан...")

                districts = get_known_districts(city)
                if not districts:
                    districts = get_districts(city)
                district_ids = list(districts.keys()) if districts else [None]

                if city_needs_deep:
                    total_combos = sum(len(subcats) for subcats in categories.values()) * len(district_ids)
                    combo_num = 0

                    for cat, subcats in categories.items():
                        if should_stop():
                            break

                        for district_id in district_ids:
                            if should_stop():
                                break

                            # ОПТИМИЗАЦИЯ: проверяем родительскую категорию
                            parent_pages = listing_parser.get_total_pages(city, "list", cat, None, district_id)
                            if parent_pages == 0:
                                # Вся категория пуста для этого района — пропускаем все подкатегории
                                district_name = districts.get(district_id, '') if district_id else 'все'
                                combo_num += len(subcats)
                                print(f"[URLs] SKIP {city}/{cat} (р-н: {district_name}) — пусто [{combo_num}/{total_combos}]")
                                time.sleep(request_delay)
                                continue

                            for subcat in subcats:
                                if should_stop():
                                    break

                                combo_num += 1
                                district_name = districts.get(district_id, '') if district_id else 'все'
                                print(f"[URLs] {city}/{cat}/{subcat} (р-н: {district_name}) [{combo_num}/{total_combos}]")

                                # Топовые
                                if not skip_top:
                                    pages = listing_parser.get_total_pages(city, "gallery", cat, subcat, district_id)
                                    if max_pages:
                                        pages = min(pages, max_pages)
                                    for page in range(1, pages + 1):
                                        if should_stop():
                                            break
                                        for url, _ in listing_parser.get_listing_urls(city, "gallery", page, cat, subcat, district_id):
                                            add_url(url, region, True)
                                        time.sleep(request_delay)

                                # Обычные
                                pages = listing_parser.get_total_pages(city, "list", cat, subcat, district_id)
                                if max_pages:
                                    pages = min(pages, max_pages)
                                for page in range(1, pages + 1):
                                    if should_stop():
                                        break
                                    for url, _ in listing_parser.get_listing_urls(city, "list", page, cat, subcat, district_id):
                                        add_url(url, region, False)
                                    time.sleep(request_delay)
                else:
                    # Простой скан
                    if not skip_top:
                        pages = listing_parser.get_total_pages(city, "gallery")
                        if max_pages:
                            pages = min(pages, max_pages)
                        for page in range(1, pages + 1):
                            if should_stop():
                                break
                            for url, _ in listing_parser.get_listing_urls(city, "gallery", page):
                                add_url(url, region, True)
                            time.sleep(request_delay)

                    pages = listing_parser.get_total_pages(city, "list")
                    if max_pages:
                        pages = min(pages, max_pages)
                    for page in range(1, pages + 1):
                        if should_stop():
                            break
                        for url, _ in listing_parser.get_listing_urls(city, "list", page):
                            add_url(url, region, False)
                        time.sleep(request_delay)

        stats['urls_found'] = count
        stats['urls_skipped'] = skipped
    finally:
        client.close()
        url_queue.put(POISON_PILL)
        print(f"[URLs] Готово: {count} новых URL, {skipped} пропущено (уже обработаны)")


# ============================================================
# Worker 2: Скачивание данных + изображений + SQL
# ============================================================

def data_worker(
    worker_id: int,
    url_queue: Queue,
    stats: dict,
    done_event: Event,
    config: PipelineConfig,
    sql_lock,
    journal_lock,
    existing_image_map: dict,
):
    """Скачивает данные, обрабатывает фото, пишет SQL сразу в файл"""
    import requests
    from PIL import Image
    from export.unisite_export import map_categories
    from export.sql_export import (
        ad_to_sql_insert, get_category_id, get_city_id, get_region_id, limit_photos
    )

    client = HttpClient()
    detail_parser = DetailParser(client)

    preview_dir = os.path.join(config.images_dir, "preview")
    others_dir = os.path.join(config.images_dir, "images")
    os.makedirs(preview_dir, exist_ok=True)
    os.makedirs(others_dir, exist_ok=True)

    processed_ads = 0
    processed_images = 0
    reused_images = 0

    def make_filename(url):
        """Детерминированное имя: один URL = одно имя"""
        return hashlib.md5(url.encode()).hexdigest()[:13] + ".webp"

    def process_image(url, is_preview):
        try:
            filename = make_filename(url)

            # Проверяем есть ли уже на диске
            if is_preview:
                filepath = os.path.join(preview_dir, filename)
            else:
                filepath = os.path.join(others_dir, filename)

            if os.path.exists(filepath):
                return filename  # Уже скачан

            # Проверяем в старом image_map (файл с другим именем)
            old_name = existing_image_map.get(url)
            if old_name:
                old_preview = os.path.join(preview_dir, old_name)
                old_other = os.path.join(others_dir, old_name)
                if os.path.exists(old_preview):
                    os.link(old_preview, filepath) if not os.path.exists(filepath) else None
                    return filename
                if os.path.exists(old_other):
                    os.link(old_other, filepath) if not os.path.exists(filepath) else None
                    return filename

            # Скачиваем
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()

            img = Image.open(io.BytesIO(resp.content))
            if img.mode != 'RGB':
                img = img.convert('RGB')

            if is_preview:
                if max(img.size) > config.preview_max_size:
                    ratio = config.preview_max_size / max(img.size)
                    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
                quality = config.preview_quality
            else:
                w, h = img.size
                img = img.crop((0, 0, w, h - config.crop_bottom_pixels))
                if max(img.size) > config.compress_max_size:
                    ratio = config.compress_max_size / max(img.size)
                    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
                quality = config.compress_quality

            buf = io.BytesIO()
            img.save(buf, format='WEBP', quality=quality)
            with open(filepath, 'wb') as f:
                f.write(buf.getvalue())

            return filename
        except Exception:
            return None

    def write_sql(ad, category_id):
        """Инкрементальная запись SQL"""
        city_id = get_city_id(ad.city) if ad.city else 0
        region_id = get_region_id(ad.region) if ad.region else 0
        sql = ad_to_sql_insert(
            ad, category_id=category_id,
            city_id=city_id, region_id=region_id,
            user_id=config.sql_user_id,
        )
        with sql_lock:
            with open(config.sql_file, 'a', encoding='utf-8') as f:
                f.write(f"-- Ad: {ad.id}\n")
                f.write(sql)
                f.write("\n\n")

    def write_journal(ad_id):
        """Записать ID в журнал"""
        with journal_lock:
            with open(config.journal_file, 'a') as f:
                f.write(f"{ad_id}\n")

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
                except Exception:
                    time.sleep(0.5)

            if not ad:
                continue

            if not ad.region:
                ad.region = region
            ad.is_top = is_top

            cat1, cat2 = map_categories(ad.category, ad.subcategory)
            category_id = get_category_id(cat1, cat2)
            photos = limit_photos(ad.photos or [], category_id, config.max_photos_other)

            # Скачиваем / переиспользуем фото
            local_photos = []
            for idx, photo_url in enumerate(photos):
                if photo_url and photo_url.startswith('http'):
                    is_preview = (idx == 0)
                    filename = process_image(photo_url, is_preview)
                    if filename:
                        local_photos.append(filename)
                        processed_images += 1
                    time.sleep(config.request_delay)

            ad.photos = local_photos

            # SQL сразу в файл
            write_sql(ad, category_id)
            write_journal(ad.id)

            processed_ads += 1
            print(f"[W{worker_id}] #{processed_ads}: {ad.id} ({len(local_photos)} фото)")

            time.sleep(config.request_delay)

    finally:
        client.close()
        stats[f'worker_{worker_id}_ads'] = processed_ads
        stats[f'worker_{worker_id}_images'] = processed_images
        print(f"[Worker {worker_id}] Завершён: {processed_ads} ads, {processed_images} images")


# ============================================================
# Главный процесс
# ============================================================

def run_pipeline(regions_to_parse: dict, config: PipelineConfig, max_pages: int = None, skip_top: bool = False, use_deep_scan: bool = True):
    """Запуск конвейера"""
    print("=" * 60)
    print("ПАРАЛЛЕЛЬНЫЙ КОНВЕЙЕР v2")
    print("=" * 60)
    print(f"Data workers: {config.data_workers}")
    print(f"Delay: {config.request_delay}s")
    print(f"Режим: {'глубокий (категории × районы)' if use_deep_scan else 'простой'}")
    print(f"Превью: quality={config.preview_quality}, max={config.preview_max_size}px")
    print(f"Остальные: crop={config.crop_bottom_pixels}px, quality={config.compress_quality}, max={config.compress_max_size}px")
    print(f"SQL: {config.sql_file} (инкрементальный)")
    print(f"Журнал: {config.journal_file}")
    if config.max_ads:
        print(f"Лимит: {config.max_ads} объявлений")
    print("=" * 60)

    # Загружаем состояние для resume
    processed_ids = load_processed_ids(config.journal_file)
    existing_image_map = load_image_map(config.image_map_file)

    manager = Manager()
    url_queue = Queue(maxsize=500)
    stats = manager.dict()
    done_event = Event()
    sql_lock = Lock()
    journal_lock = Lock()

    os.makedirs(config.images_dir, exist_ok=True)

    # Инициализируем SQL файл (если новый)
    if not os.path.exists(config.sql_file):
        with open(config.sql_file, 'w', encoding='utf-8') as f:
            f.write("-- SQL Export from ads-parser v2 (incremental)\n")
            f.write(f"-- Started: {datetime.now().isoformat()}\n\n")
            f.write("SET NAMES utf8mb4;\n\n")

    processes = []

    # URL Parser
    p = Process(target=url_parser_worker, args=(
        regions_to_parse, url_queue, stats, max_pages, skip_top,
        config.request_delay, config.max_ads, use_deep_scan, processed_ids
    ))
    p.start()
    processes.append(p)

    # Data workers
    time.sleep(1)
    for i in range(config.data_workers):
        p = Process(target=data_worker, args=(
            i, url_queue, stats, done_event, config,
            sql_lock, journal_lock, existing_image_map,
        ))
        p.start()
        processes.append(p)

    # Ждём
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[Main] Прерывание... данные уже сохранены в SQL и журнале")
        done_event.set()
        for p in processes:
            p.terminate()

    # Итоги
    total_ads = sum(stats.get(f'worker_{i}_ads', 0) for i in range(config.data_workers))
    total_imgs = sum(stats.get(f'worker_{i}_images', 0) for i in range(config.data_workers))

    print("\n" + "=" * 60)
    print("ГОТОВО")
    print("=" * 60)
    print(f"Новых объявлений: {total_ads}")
    print(f"Изображений: {total_imgs}")
    print(f"SQL: {config.sql_file}")
    print(f"Журнал: {config.journal_file}")
    print(f"Images: {config.images_dir}/")
    print("=" * 60)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Параллельный конвейер v2")
    parser.add_argument("-r", "--region", choices=["ДНР", "ЛНР", "Запорожье", "Херсон"])
    parser.add_argument("-c", "--city")
    parser.add_argument("-p", "--max-pages", type=int)
    parser.add_argument("--skip-top", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--preview-quality", type=int, default=90)
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument("--crop", type=int, default=100)
    parser.add_argument("--user-id", type=int, default=4173)
    parser.add_argument("-d", "--images-dir", default="./images")
    parser.add_argument("-o", "--output", default="./export.sql")
    parser.add_argument("--journal", default="./processed_ids.txt", help="Журнал обработанных ID")
    parser.add_argument("--image-map", default="./image_map.json", help="Маппинг URL→файл от прошлого запуска")
    parser.add_argument("--skip-cities", help="Пропустить города (через запятую)")

    scan_group = parser.add_mutually_exclusive_group()
    scan_group.add_argument("--deep-scan", action="store_true", default=True)
    scan_group.add_argument("--simple-scan", action="store_true")

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
        journal_file=args.journal,
        image_map_file=args.image_map,
    )

    use_deep_scan = not args.simple_scan

    if args.test:
        args.city = "donetsk"
        args.max_pages = 1
        config.max_ads = 10
        use_deep_scan = False

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

    # Фильтруем пропускаемые города
    if args.skip_cities:
        skip_set = set(c.strip() for c in args.skip_cities.split(","))
        regions = {
            r: [c for c in cities if c not in skip_set]
            for r, cities in regions.items()
        }
        regions = {r: c for r, c in regions.items() if c}  # убираем пустые регионы
        print(f"[Config] Пропускаем города: {skip_set}")

    run_pipeline(regions, config, args.max_pages, args.skip_top, use_deep_scan)


if __name__ == "__main__":
    main()
