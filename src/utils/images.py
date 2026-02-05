"""Скачивание изображений"""

import os
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

from models import Ad
from parser.client import HttpClient
from config import IMAGES_DIR


def get_image_filename(url: str) -> str:
    """Получить имя файла из URL"""
    parsed = urlparse(url)
    return os.path.basename(parsed.path) or "image.jpg"


def download_images(
    urls: Sequence[str],
    output_dir: str,
    client: HttpClient,
) -> list[str]:
    """
    Скачать изображения

    Args:
        urls: Список URL изображений
        output_dir: Директория для сохранения
        client: HTTP клиент

    Returns:
        Список путей к скачанным файлам
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    downloaded = []

    for i, url in enumerate(urls):
        filename = get_image_filename(url)
        # Добавляем индекс для уникальности
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{i}{ext}"

        filepath = os.path.join(output_dir, filename)

        if client.download(url, filepath):
            downloaded.append(filepath)
            print(f"  Скачано: {filename}")
        else:
            print(f"  Ошибка: {url}")

    return downloaded


def download_ad_images(
    ad: Ad,
    base_dir: str = IMAGES_DIR,
    client: HttpClient = None,
) -> list[str]:
    """
    Скачать все фото объявления

    Args:
        ad: Объявление
        base_dir: Базовая директория для изображений
        client: HTTP клиент (создастся если не передан)

    Returns:
        Список путей к скачанным файлам
    """
    if not ad.photos:
        return []

    output_dir = os.path.join(base_dir, ad.id)

    own_client = client is None
    if own_client:
        client = HttpClient()

    try:
        return download_images(ad.photos, output_dir, client)
    finally:
        if own_client:
            client.close()
