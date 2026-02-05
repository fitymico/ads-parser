#!/usr/bin/env python3
"""Главный скрипт парсера dnr.red"""

import argparse
import re
import sys
import os
from typing import Optional

# Добавляем путь к src в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CITIES, OUTPUT_FILE
from models import Ad
from parser.client import HttpClient
from parser.listing import ListingParser
from parser.detail import DetailParser
from mapper.cities import get_city_region
from export.csv_export import export_to_csv, load_existing_ids, append_to_csv
from export.unisite_export import export_to_unisite, load_existing_ids_unisite
from export.sql_export import export_to_sql, load_existing_import_ids


def collect_urls(
    listing_parser: ListingParser,
    regions_to_parse: dict[str, list[str]],
    existing_ids: set[str],
    max_pages: Optional[int] = None,
    skip_top: bool = False,
) -> list[tuple[str, str, bool]]:
    """
    Фаза 1: Сбор всех URL объявлений

    Returns:
        Список кортежей (url, region, is_top)
    """
    all_urls = []  # (url, region, is_top)
    seen_ids = set(existing_ids)

    for region, cities in regions_to_parse.items():
        print(f"\n{'='*60}")
        print(f"РЕГИОН: {region}")
        print("=" * 60)

        for city in cities:
            print(f"\n  Город: {city}")

            # 1. ТОП объявления (gallery)
            if skip_top:
                print("    [ТОП] - пропущено")
            else:
                top_pages = listing_parser.get_total_pages(city, "gallery")
                if max_pages:
                    top_pages = min(top_pages, max_pages)
                print(f"    [ТОП] страниц: {top_pages}")

                top_count = 0
                for page in range(1, top_pages + 1):
                    items = listing_parser.get_listing_urls(city, "gallery", page)
                    for url, _ in items:
                        match = re.search(r'-(\d{5,})\.html$', url)
                        ad_id = match.group(1) if match else ""
                        if ad_id and ad_id not in seen_ids:
                            seen_ids.add(ad_id)
                            all_urls.append((url, region, True))
                            top_count += 1
                print(f"    [ТОП] найдено: {top_count}")

            # 2. Обычные объявления (list)
            list_pages = listing_parser.get_total_pages(city, "list")
            if max_pages:
                list_pages = min(list_pages, max_pages)
            print(f"    [ОБЫЧНЫЕ] страниц: {list_pages}")

            regular_count = 0
            for page in range(1, list_pages + 1):
                items = listing_parser.get_listing_urls(city, "list", page)
                for url, _ in items:
                    match = re.search(r'-(\d{5,})\.html$', url)
                    ad_id = match.group(1) if match else ""
                    if ad_id and ad_id not in seen_ids:
                        seen_ids.add(ad_id)
                        all_urls.append((url, region, False))
                        regular_count += 1
            print(f"    [ОБЫЧНЫЕ] найдено: {regular_count}")

    return all_urls


def parse_ads(
    detail_parser: DetailParser,
    urls: list[tuple[str, str, bool]],
) -> list[Ad]:
    """
    Фаза 2: Парсинг деталей объявлений по собранным URL

    Args:
        urls: Список кортежей (url, region, is_top)

    Returns:
        Список объявлений
    """
    ads = []
    total = len(urls)

    print(f"\n{'='*60}")
    print(f"ПАРСИНГ ОБЪЯВЛЕНИЙ: {total}")
    print("=" * 60)

    for i, (url, region, is_top) in enumerate(urls):
        tag = "[TOP]" if is_top else ""
        print(f"  [{i+1}/{total}] {tag} {url.split('/')[-1][:50]}...")

        ad = detail_parser.parse(url)
        if ad:
            if not ad.region:
                ad.region = region
            ad.is_top = is_top
            ads.append(ad)

    return ads


def main():
    parser = argparse.ArgumentParser(
        description="Парсер объявлений dnr.red"
    )
    parser.add_argument(
        "-r", "--region",
        choices=["ДНР", "ЛНР", "Запорожье", "Херсон"],
        help="Парсить только указанный регион",
    )
    parser.add_argument(
        "-c", "--city",
        help="Парсить только указанный город (slug)",
    )
    parser.add_argument(
        "-p", "--max-pages",
        type=int,
        default=None,
        help="Максимум страниц на город",
    )
    parser.add_argument(
        "-o", "--output",
        default=OUTPUT_FILE,
        help=f"Выходной CSV файл (по умолчанию: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Добавить к существующему файлу (не перезаписывать)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Тестовый режим: 1 город, 1 страница",
    )
    parser.add_argument(
        "--skip-top",
        action="store_true",
        help="Пропустить топ-объявления (парсить только обычные)",
    )
    parser.add_argument(
        "--unisite",
        action="store_true",
        help="Экспорт в формат UniSite (разделитель ;)",
    )
    parser.add_argument(
        "--sql",
        action="store_true",
        help="Экспорт в SQL INSERT-запросы для nulled_ads",
    )
    parser.add_argument(
        "--sql-user-id",
        type=int,
        default=1,
        help="ID пользователя-владельца для SQL (по умолчанию: 1)",
    )

    args = parser.parse_args()

    # Загружаем существующие ID если добавляем
    existing_ids = set()
    if args.append:
        if args.sql:
            existing_ids = load_existing_import_ids(args.output)
        elif args.unisite:
            existing_ids = load_existing_ids_unisite(args.output)
        else:
            existing_ids = load_existing_ids(args.output)
        if existing_ids:
            print(f"Загружено {len(existing_ids)} существующих объявлений")

    # Определяем что парсить
    if args.test:
        args.city = "donetsk"
        args.max_pages = 1

    if args.city:
        region = get_city_region(args.city)
        if not region:
            print(f"Неизвестный город: {args.city}")
            sys.exit(1)
        regions_to_parse = {region: [args.city]}
    elif args.region:
        regions_to_parse = {args.region: CITIES[args.region]}
    else:
        regions_to_parse = CITIES

    print("=" * 60)
    print("Парсер объявлений dnr.red")
    print("=" * 60)
    print(f"Регионы: {list(regions_to_parse.keys())}")
    total_cities = sum(len(c) for c in regions_to_parse.values())
    print(f"Городов: {total_cities}")
    print(f"Выходной файл: {args.output}")
    print("=" * 60)

    # Создаём клиент и парсеры
    client = HttpClient()
    listing_parser = ListingParser(client)
    detail_parser = DetailParser(client)

    try:
        # Фаза 1: Сбор всех URL
        print("\n" + "=" * 60)
        print("ФАЗА 1: СБОР URL")
        print("=" * 60)

        urls = collect_urls(
            listing_parser,
            regions_to_parse,
            existing_ids,
            args.max_pages,
            args.skip_top,
        )

        top_urls = sum(1 for _, _, is_top in urls if is_top)
        regular_urls = len(urls) - top_urls
        print(f"\n{'='*60}")
        print(f"СОБРАНО URL: {len(urls)} (топ: {top_urls}, обычные: {regular_urls})")
        print("=" * 60)

        if not urls:
            print("\nНовых объявлений не найдено")
            return

        # Фаза 2: Парсинг деталей
        print("\n" + "=" * 60)
        print("ФАЗА 2: ПАРСИНГ ДЕТАЛЕЙ")
        print("=" * 60)

        all_ads = parse_ads(detail_parser, urls)

        # Экспорт
        if all_ads:
            if args.sql:
                # SQL экспорт
                output = args.output
                if not output.endswith(".sql"):
                    output = output.rsplit(".", 1)[0] + ".sql"
                count = export_to_sql(all_ads, output, user_id=args.sql_user_id)
                fmt = "SQL"
                print(f"\n{'='*60}")
                print(f"ВНИМАНИЕ: Перед выполнением SQL проверьте маппинги!")
                print(f"Используется INSERT IGNORE - дубликаты будут пропущены")
                print("=" * 60)
            elif args.unisite:
                # Меняем расширение на .csv если указан другой файл
                output = args.output
                if not output.endswith(".csv"):
                    output = output.rsplit(".", 1)[0] + ".csv"
                count = export_to_unisite(all_ads, output, append=args.append)
                fmt = "UniSite"
            elif args.append and existing_ids:
                count = append_to_csv(all_ads, args.output)
                output = args.output
                fmt = "CSV"
            else:
                count = export_to_csv(all_ads, args.output)
                output = args.output
                fmt = "CSV"

            print(f"\n{'='*60}")
            print(f"ИТОГО: {count} объявлений сохранено в {output} ({fmt})")
            print("=" * 60)
        else:
            print("\nНе удалось спарсить объявления")

    finally:
        client.close()


if __name__ == "__main__":
    main()
