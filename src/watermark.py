#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Наложение водяного знака на превью изображения.

Использование:
  # Тест на одном файле
  python watermark.py --test preview/abc123.webp

  # Обработать всю папку
  python watermark.py --dir /data/images/preview/

  # Следить за папкой (демон) — обрабатывает новые файлы
  python watermark.py --watch /data/images/preview/
"""

import argparse
import os
import sys
import time
from pathlib import Path

from PIL import Image
import numpy as np


def load_watermark(path: str) -> Image.Image:
    """
    Загрузить водяной знак и убрать белый фон только по краям (flood fill от углов).

    Returns:
        RGBA изображение с прозрачным фоном по краям
    """
    wm = Image.open(path).convert('RGBA')
    data = np.array(wm)
    h, w = data.shape[:2]

    # Flood fill от краёв: убираем белый фон только связанный с границей
    from scipy.ndimage import label
    white_mask = (data[:, :, 0] > 220) & (data[:, :, 1] > 220) & (data[:, :, 2] > 220)

    # Находим связные области белых пикселей
    labeled, num_features = label(white_mask)

    # Находим метки, которые касаются границ изображения
    border_labels = set()
    border_labels.update(labeled[0, :].tolist())      # верхний край
    border_labels.update(labeled[-1, :].tolist())     # нижний край
    border_labels.update(labeled[:, 0].tolist())      # левый край
    border_labels.update(labeled[:, -1].tolist())     # правый край
    border_labels.discard(0)  # 0 = не белый

    # Убираем только белые области касающиеся границ
    edge_white = np.zeros_like(white_mask)
    for lbl in border_labels:
        edge_white |= (labeled == lbl)

    data[edge_white, 3] = 0

    return Image.fromarray(data, 'RGBA')


def apply_watermark(
    img: Image.Image,
    watermark: Image.Image,
    wm_width_px: int = 116,
    padding_right: int = 8,
    padding_bottom: int = 11,
) -> Image.Image:
    """
    Наложить водяной знак на изображение (правый нижний угол,
    пиксель-в-пиксель с позицией и размером DNR.RED watermark: 82x71, right=11, bottom=15).
    """
    img = img.convert('RGBA')

    # Фиксированный размер как у DNR.RED (82px ширина)
    ratio = wm_width_px / watermark.width
    wm = watermark.resize(
        (wm_width_px, int(watermark.height * ratio)),
        Image.Resampling.LANCZOS
    )

    # Позиция: правый нижний угол, отступы как у DNR.RED
    x = img.width - wm.width - padding_right
    y = img.height - wm.height - padding_bottom

    # Накладываем
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    layer.paste(wm, (x, y))
    result = Image.alpha_composite(img, layer)

    return result.convert('RGB')


# Маркер файл чтобы не обрабатывать повторно
MARKER_SUFFIX = ".wm"


def is_processed(filepath: str, done_dir: str = None) -> bool:
    """Проверить обработан ли файл"""
    marker = filepath + MARKER_SUFFIX
    return os.path.exists(marker)


def mark_processed(filepath: str):
    """Отметить файл как обработанный"""
    marker = filepath + MARKER_SUFFIX
    Path(marker).touch()


def process_file(filepath: str, watermark: Image.Image, quality: int = 90) -> bool:
    """Обработать один файл"""
    try:
        img = Image.open(filepath)
        result = apply_watermark(img, watermark)
        result.save(filepath, format='WEBP', quality=quality)
        mark_processed(filepath)
        return True
    except Exception as e:
        print(f"[WM] Ошибка {filepath}: {e}")
        return False


def process_directory(directory: str, watermark_path: str, quality: int = 90):
    """Обработать все файлы в папке"""
    wm = load_watermark(watermark_path)
    files = [f for f in os.listdir(directory) if f.endswith('.webp')]
    total = len(files)
    processed = 0
    skipped = 0

    for i, filename in enumerate(files):
        filepath = os.path.join(directory, filename)
        if is_processed(filepath):
            skipped += 1
            continue

        if process_file(filepath, wm, quality):
            processed += 1

        if (processed + skipped) % 100 == 0:
            print(f"[WM] {processed + skipped}/{total} (обработано: {processed}, пропущено: {skipped})")

    print(f"[WM] Готово: {processed} обработано, {skipped} пропущено из {total}")


def watch_directory(directory: str, watermark_path: str, quality: int = 90, interval: float = 5.0):
    """Следить за папкой и обрабатывать новые файлы"""
    wm = load_watermark(watermark_path)
    processed = 0
    print(f"[WM] Слежу за {directory} (интервал {interval}с)")

    while True:
        files = [f for f in os.listdir(directory) if f.endswith('.webp')]
        new_files = 0

        for filename in files:
            filepath = os.path.join(directory, filename)
            if is_processed(filepath):
                continue

            if process_file(filepath, wm, quality):
                processed += 1
                new_files += 1

        if new_files:
            print(f"[WM] +{new_files} (всего: {processed})")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Watermark processor")
    parser.add_argument("--watermark", "-w", default="WaterMark.png", help="Путь к водяному знаку")
    parser.add_argument("--quality", "-q", type=int, default=90)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", "-t", help="Тест на одном файле")
    group.add_argument("--dir", "-d", help="Обработать папку")
    group.add_argument("--watch", help="Следить за папкой (демон)")

    args = parser.parse_args()

    # Ищем водяной знак
    wm_path = args.watermark
    if not os.path.exists(wm_path):
        # Пробуем относительно скрипта
        script_dir = os.path.dirname(os.path.abspath(__file__))
        wm_path = os.path.join(script_dir, '..', args.watermark)
    if not os.path.exists(wm_path):
        print(f"Водяной знак не найден: {args.watermark}")
        sys.exit(1)

    if args.test:
        wm = load_watermark(wm_path)
        img = Image.open(args.test)
        result = apply_watermark(img, wm)
        out_path = args.test.rsplit('.', 1)[0] + '_wm.webp'
        result.save(out_path, format='WEBP', quality=args.quality)
        print(f"Сохранено: {out_path}")

    elif args.dir:
        process_directory(args.dir, wm_path, args.quality)

    elif args.watch:
        watch_directory(args.watch, wm_path, args.quality)


if __name__ == "__main__":
    main()
