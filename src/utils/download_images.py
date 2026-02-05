"""Скрипт для скачивания изображений и подготовки к SQL импорту"""

import hashlib
import io
import os
import re
import json
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

# PIL для сжатия изображений (опционально)
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# LAMA для удаления водяных знаков (опционально)
try:
    from simple_lama_inpainting import SimpleLama
    LAMA_AVAILABLE = True
    _lama_model = None  # Lazy loading
except ImportError:
    LAMA_AVAILABLE = False
    _lama_model = None


def get_lama_model():
    """Получить модель LAMA (lazy loading)"""
    global _lama_model
    if _lama_model is None and LAMA_AVAILABLE:
        print("  Загрузка модели LAMA...")
        _lama_model = SimpleLama()
    return _lama_model


def remove_watermark(
    image: Image.Image,
    wm_width: int = 80,
    wm_height: int = 80,
    offset_right: int = 15,
    offset_bottom: int = 20,
    padding: int = 10,
) -> Image.Image:
    """
    Удалить водяной знак с изображения используя LAMA inpainting

    Водяной знак находится справа снизу.

    Args:
        image: PIL изображение
        wm_width: Ширина водяного знака
        wm_height: Высота водяного знака
        offset_right: Отступ от правого края
        offset_bottom: Отступ от нижнего края
        padding: Дополнительный отступ вокруг для удаления рамки

    Returns:
        Изображение без водяного знака
    """
    if not LAMA_AVAILABLE:
        return image

    lama = get_lama_model()
    if lama is None:
        return image

    try:
        w, h = image.size

        # Координаты области водяного знака с padding
        x1 = max(0, w - offset_right - wm_width - padding)
        y1 = max(0, h - offset_bottom - wm_height - padding)
        x2 = min(w, w - offset_right + padding)
        y2 = min(h, h - offset_bottom + padding)

        # Создаём маску (белая область = область для inpainting)
        mask = Image.new('L', (w, h), 0)
        for y in range(y1, y2):
            for x in range(x1, x2):
                mask.putpixel((x, y), 255)

        # Применяем inpainting
        result = lama(image, mask)
        return result

    except Exception as e:
        print(f"    Ошибка удаления водяного знака: {e}")
        return image


def compress_image(
    image_data: bytes,
    max_size: int = 1200,
    quality: int = 75,
    format: str = 'webp',
) -> bytes:
    """
    Сжать изображение

    Args:
        image_data: Исходные данные изображения
        max_size: Максимальный размер по большей стороне
        quality: Качество JPEG/WebP (1-100)
        format: Формат выхода (webp, jpeg)

    Returns:
        Сжатые данные изображения
    """
    if not PIL_AVAILABLE:
        return image_data

    try:
        img = Image.open(io.BytesIO(image_data))

        # Конвертируем RGBA в RGB для JPEG/WebP
        if img.mode in ('RGBA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Уменьшаем размер если нужно
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Сохраняем со сжатием
        output = io.BytesIO()
        if format.lower() == 'webp':
            img.save(output, format='WEBP', quality=quality, method=4)
        else:
            img.save(output, format='JPEG', quality=quality, optimize=True)

        return output.getvalue()

    except Exception as e:
        print(f"    Ошибка сжатия: {e}")
        return image_data


def generate_filename(url: str, extension: str = None) -> str:
    """
    Генерировать уникальное имя файла как в платформе

    Формат: хэш из 13 символов + расширение
    """
    # Генерируем хэш от URL + timestamp для уникальности
    hash_input = f"{url}{time.time()}"
    file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:13]

    # Определяем расширение
    if not extension:
        parsed = urlparse(url)
        path = parsed.path.lower()
        if '.webp' in path:
            extension = 'webp'
        elif '.png' in path:
            extension = 'png'
        elif '.gif' in path:
            extension = 'gif'
        elif '.jpeg' in path or '.jpg' in path:
            extension = 'webp'  # Конвертируем в webp как платформа
        else:
            extension = 'webp'

    return f"{file_hash}.{extension}"


def download_image(
    url: str,
    output_dir: str,
    timeout: int = 30,
    compress: bool = False,
    compress_quality: int = 75,
    compress_max_size: int = 1200,
    remove_watermark_enabled: bool = False,
) -> Optional[str]:
    """
    Скачать изображение и сохранить с уникальным именем

    Конвейер обработки:
    1. Скачивание
    2. Удаление водяного знака (LAMA) - если включено
    3. Сжатие - если включено

    Args:
        url: URL изображения
        output_dir: Директория для сохранения
        timeout: Таймаут запроса
        compress: Сжимать ли изображение
        compress_quality: Качество сжатия (1-100)
        compress_max_size: Максимальный размер по большей стороне
        remove_watermark_enabled: Удалять водяной знак через LAMA

    Returns:
        Имя файла или None при ошибке
    """
    try:
        # 1. СКАЧИВАНИЕ
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        image_data = response.content

        # Определяем тип контента
        content_type = response.headers.get('Content-Type', '')
        if 'gif' in content_type:
            ext = 'gif'
            # GIF не обрабатываем
            compress = False
            remove_watermark_enabled = False
        elif 'png' in content_type:
            ext = 'webp'  # Конвертируем в webp
        elif 'webp' in content_type:
            ext = 'webp'
        else:
            ext = 'webp'

        # 2. УДАЛЕНИЕ ВОДЯНОГО ЗНАКА
        if remove_watermark_enabled and PIL_AVAILABLE and LAMA_AVAILABLE:
            img = Image.open(io.BytesIO(image_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img = remove_watermark(img)  # Используем параметры по умолчанию (80x80, offset 15x20, padding 10)
            # Сохраняем в bytes с высоким качеством для последующего сжатия
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='WEBP', quality=95)
            image_data = output_buffer.getvalue()
            print(f"    [wm removed]", end='')

        # 3. СЖАТИЕ
        if compress and PIL_AVAILABLE:
            original_size = len(image_data)
            image_data = compress_image(
                image_data,
                max_size=compress_max_size,
                quality=compress_quality,
                format=ext,
            )
            compressed_size = len(image_data)
            if compressed_size < original_size:
                ratio = (1 - compressed_size / original_size) * 100
                print(f" [сжато: -{ratio:.0f}%]", end='')

        filename = generate_filename(url, ext)
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(image_data)

        return filename

    except Exception as e:
        print(f"Ошибка скачивания {url}: {e}")
        return None


def process_sql_file(
    input_sql: str,
    output_sql: str,
    images_dir: str,
    download: bool = True,
    compress_non_preview: bool = True,
    compress_quality: int = 75,
    compress_max_size: int = 1200,
    remove_watermark: bool = False,
) -> dict:
    """
    Обработать SQL файл: скачать изображения и заменить URL на локальные имена

    Конвейер для каждого изображения:
    1. Скачивание
    2. Удаление водяного знака (LAMA) - 80x80px, справа снизу
    3. Сжатие (для не-превью)

    Args:
        input_sql: Путь к исходному SQL файлу
        output_sql: Путь к выходному SQL файлу
        images_dir: Директория для изображений
        download: Скачивать ли изображения (False = только замена имён)
        compress_non_preview: Сжимать не-превью изображения
        compress_quality: Качество сжатия
        compress_max_size: Максимальный размер
        remove_watermark: Удалять водяной знак через LAMA

    Returns:
        Статистика обработки
    """
    os.makedirs(images_dir, exist_ok=True)

    stats = {
        'total_images': 0,
        'downloaded': 0,
        'failed': 0,
        'cached': 0,
        'compressed': 0,
        'watermark_removed': 0,
    }

    # Кэш URL -> filename для избежания повторного скачивания
    url_cache = {}

    with open(input_sql, 'r', encoding='utf-8') as f:
        content = f.read()

    def replace_url_array(match):
        """Заменить JSON массив URL на массив локальных имён"""
        array_str = match.group(0)

        try:
            # Убираем экранирование для парсинга
            clean_str = array_str.replace('\\"', '"')
            urls = json.loads(clean_str)

            new_names = []
            for idx, url in enumerate(urls):
                stats['total_images'] += 1
                is_preview = (idx == 0)  # Первое изображение - превью

                if url in url_cache:
                    new_names.append(url_cache[url])
                    stats['cached'] += 1
                    continue

                if download and url.startswith('http'):
                    # Превью не сжимаем, остальные сжимаем
                    should_compress = compress_non_preview and not is_preview
                    tag = "[PREVIEW]" if is_preview else f"[{idx+1}]"

                    filename = download_image(
                        url,
                        images_dir,
                        compress=should_compress,
                        compress_quality=compress_quality,
                        compress_max_size=compress_max_size,
                        remove_watermark_enabled=remove_watermark,
                    )
                    if filename:
                        new_names.append(filename)
                        url_cache[url] = filename
                        stats['downloaded'] += 1
                        if should_compress:
                            stats['compressed'] += 1
                        if remove_watermark:
                            stats['watermark_removed'] += 1
                        print(f"  ✓ {tag} {filename}")
                    else:
                        stats['failed'] += 1
                else:
                    # Генерируем имя без скачивания
                    filename = generate_filename(url)
                    new_names.append(filename)
                    url_cache[url] = filename

            # Формируем новый JSON массив
            new_array = json.dumps(new_names, ensure_ascii=False)
            return new_array.replace('"', '\\"')

        except json.JSONDecodeError:
            return array_str

    # Заменяем все JSON массивы с URL
    # Паттерн: ["https://...", "https://..."]
    pattern = r'\["https?:[^\]]+\]'
    new_content = re.sub(pattern, replace_url_array, content)

    with open(output_sql, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Скачивание изображений для SQL импорта'
    )
    parser.add_argument('input_sql', help='Входной SQL файл')
    parser.add_argument('-o', '--output', help='Выходной SQL файл')
    parser.add_argument(
        '-d', '--images-dir',
        default='./uploaded_images',
        help='Директория для изображений'
    )
    parser.add_argument(
        '--no-download',
        action='store_true',
        help='Только заменить URL на имена файлов (без скачивания)'
    )
    parser.add_argument(
        '--no-compress',
        action='store_true',
        help='Не сжимать изображения (по умолчанию: сжатие включено)'
    )
    parser.add_argument(
        '--quality',
        type=int,
        default=75,
        help='Качество сжатия WebP/JPEG (1-100, по умолчанию: 75)'
    )
    parser.add_argument(
        '--max-size',
        type=int,
        default=1200,
        help='Максимальный размер изображения в пикселях (по умолчанию: 1200)'
    )
    parser.add_argument(
        '--remove-watermark',
        action='store_true',
        help='Удалять водяной знак (80x80, справа снизу) через LAMA'
    )

    args = parser.parse_args()

    output = args.output or args.input_sql.replace('.sql', '_processed.sql')

    compress = not args.no_compress
    compress_status = 'Нет' if args.no_compress else f'Да (качество: {args.quality}, макс: {args.max_size}px)'
    watermark_status = 'Да (80x80, справа снизу)' if args.remove_watermark else 'Нет'

    print(f"Входной файл: {args.input_sql}")
    print(f"Выходной файл: {output}")
    print(f"Директория изображений: {args.images_dir}")
    print()
    print("Конвейер обработки:")
    print(f"  1. Скачивание: {'Нет' if args.no_download else 'Да'}")
    print(f"  2. Удаление водяного знака: {watermark_status}")
    print(f"  3. Сжатие не-превью: {compress_status}")
    if compress and not PIL_AVAILABLE:
        print("     ⚠ PIL/Pillow не установлен, сжатие отключено")
    if args.remove_watermark and not LAMA_AVAILABLE:
        print("     ⚠ simple-lama-inpainting не установлен, удаление водяного знака отключено")
    print()

    stats = process_sql_file(
        args.input_sql,
        output,
        args.images_dir,
        download=not args.no_download,
        compress_non_preview=compress,
        compress_quality=args.quality,
        compress_max_size=args.max_size,
        remove_watermark=args.remove_watermark,
    )

    print()
    print("=" * 40)
    print(f"Всего изображений: {stats['total_images']}")
    print(f"Скачано: {stats['downloaded']}")
    print(f"Сжато: {stats['compressed']}")
    print(f"Водяной знак удалён: {stats['watermark_removed']}")
    print(f"Из кэша: {stats['cached']}")
    print(f"Ошибок: {stats['failed']}")
    print("=" * 40)
    print(f"\nГотово! Результат: {output}")
    print(f"Изображения: {args.images_dir}/")
    print("\nНе забудьте скопировать изображения на сервер в папку uploads!")


if __name__ == '__main__':
    main()
