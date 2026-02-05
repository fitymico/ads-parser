"""Экспорт объявлений в CSV"""

import csv
from typing import Sequence

from models import Ad


CSV_FIELDS = [
    "id",
    "title",
    "description",
    "price",
    "currency",
    "photos",
    "phone",
    "seller_name",
    "telegram",
    "city",
    "district",
    "region",
    "category",
    "subcategory",
    "date",
    "url",
    "is_top",
]


def export_to_csv(ads: Sequence[Ad], filename: str) -> int:
    """
    Экспортировать объявления в CSV файл

    Args:
        ads: Список объявлений
        filename: Путь к файлу

    Returns:
        Количество записанных объявлений
    """
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for ad in ads:
            writer.writerow(ad.to_dict())

    return len(ads)


def append_to_csv(ads: Sequence[Ad], filename: str) -> int:
    """
    Добавить объявления в существующий CSV файл

    Args:
        ads: Список объявлений
        filename: Путь к файлу

    Returns:
        Количество добавленных объявлений
    """
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)

        for ad in ads:
            writer.writerow(ad.to_dict())

    return len(ads)


def load_existing_ids(filename: str) -> set[str]:
    """
    Загрузить ID уже спарсенных объявлений

    Args:
        filename: Путь к CSV файлу

    Returns:
        Множество ID объявлений
    """
    ids = set()

    try:
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "id" in row:
                    ids.add(row["id"])
    except FileNotFoundError:
        pass

    return ids
