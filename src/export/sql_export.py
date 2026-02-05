"""Экспорт объявлений в SQL INSERT-запросы для nulled_ads"""

import json
import re
from datetime import datetime
from typing import Optional, Sequence

from models import Ad


def escape_sql(value: Optional[str]) -> str:
    """
    Безопасное экранирование строки для SQL

    Защита от SQL-инъекций:
    - Экранирует одинарные кавычки
    - Экранирует обратные слэши
    - Обрабатывает NULL
    """
    if value is None:
        return "NULL"

    # Экранирование специальных символов
    escaped = value.replace("\\", "\\\\")  # Сначала слэши
    escaped = escaped.replace("'", "\\'")  # Потом кавычки
    escaped = escaped.replace("\n", "\\n")
    escaped = escaped.replace("\r", "\\r")
    escaped = escaped.replace("\t", "\\t")
    escaped = escaped.replace("\x00", "")  # Убираем NULL-байты

    return f"'{escaped}'"


def escape_sql_or_empty(value: Optional[str]) -> str:
    """Экранирование с пустой строкой вместо NULL"""
    if value is None or value == "":
        return "''"
    return escape_sql(value)


def parse_price(price_str: Optional[str]) -> float:
    """Извлечь числовую цену из строки"""
    if not price_str:
        return 0.0

    # Убираем все нецифровые символы кроме точки и запятой
    cleaned = re.sub(r'[^\d.,]', '', price_str)
    # Заменяем запятую на точку
    cleaned = cleaned.replace(',', '.')
    # Если несколько точек - оставляем последнюю как десятичный разделитель
    parts = cleaned.split('.')
    if len(parts) > 2:
        cleaned = ''.join(parts[:-1]) + '.' + parts[-1]

    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def format_datetime_today() -> str:
    """Возвращает сегодняшнюю дату в MySQL TIMESTAMP формат"""
    return f"'{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'"


def clean_description(description: str, phone: str = None, seller_name: str = None) -> str:
    """
    Очистить описание от телефонов с эмоджи и добавить контакты в конец

    - Удаляет паттерны типа +79490197..📲+79490197..📲
    - Удаляет телефоны с эмоджи 📲📞☎️
    - Сохраняет переносы строк
    - Добавляет контактную информацию в конец
    """
    if not description:
        return ""

    text = description

    # Удаляем телефоны с эмоджи (паттерн: +7949... + эмоджи)
    # Паттерн для телефона с эмоджи рядом
    phone_emoji_pattern = r'[\+]?[78]?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}[\s\.]*[📲📞☎️📱]+'
    text = re.sub(phone_emoji_pattern, '', text)

    # Удаляем повторяющиеся эмоджи телефонов
    text = re.sub(r'[📲📞☎️📱]+', '', text)

    # Удаляем паттерн "телефон для связи :+79494203..📲+7949"
    text = re.sub(r'телефон[а-я\s]*:?\s*[\+\d\.\s\-]+[📲📞☎️📱]*[\+\d\.\s\-]*', '', text, flags=re.IGNORECASE)

    # Убираем множественные пробелы (но сохраняем переносы строк)
    text = re.sub(r'[^\S\n]+', ' ', text)  # Пробелы кроме \n -> один пробел
    text = re.sub(r'\n{3,}', '\n\n', text)  # Много переносов -> два максимум
    text = text.strip()

    # Добавляем контакты в конец
    contacts = []
    if phone:
        # Очищаем телефон от лишних символов
        clean_phone = re.sub(r'[^\d\+]', '', phone)
        if clean_phone:
            contacts.append(f"Тел: {clean_phone}")
    if seller_name:
        contacts.append(f"Контакт: {seller_name}")

    if contacts:
        text = text.rstrip('.,:;') + '\n\n' + '\n'.join(contacts)

    return text


def limit_photos(photos: list[str], category_id: int, max_other: int = 3) -> list[str]:
    """
    Ограничить количество фото для категорий не недвижимость/авто

    Args:
        photos: список фото
        category_id: ID категории
        max_other: максимум фото для прочих категорий

    Returns:
        Ограниченный список фото
    """
    if not photos:
        return []

    # ID категорий недвижимости и транспорта
    REALTY_CATEGORIES = {18, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 159}
    TRANSPORT_CATEGORIES = {17, 27, 30, 31, 247, 248, 249}

    # Для недвижимости и транспорта - без ограничений
    if category_id in REALTY_CATEGORIES or category_id in TRANSPORT_CATEGORIES:
        return photos

    # Для остальных - ограничиваем
    return photos[:max_other]


def photos_to_json(photos: list[str]) -> str:
    """Конвертировать список фото в JSON для ads_images"""
    if not photos:
        return "''"

    # Формат: JSON массив путей или URL
    # В БД хранится как JSON: ["path1.jpg", "path2.jpg"]
    return escape_sql(json.dumps(photos, ensure_ascii=False))


def generate_alias(title: str, ad_id: str) -> str:
    """Генерировать URL-alias из заголовка"""
    if not title:
        return ad_id

    # Транслитерация
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }

    result = []
    for char in title.lower():
        if char in translit_map:
            result.append(translit_map[char])
        elif char.isalnum():
            result.append(char)
        elif char in ' -_':
            result.append('-')

    alias = ''.join(result)
    # Убираем множественные дефисы
    alias = re.sub(r'-+', '-', alias).strip('-')
    # Ограничиваем длину и добавляем ID
    alias = alias[:100] + '-' + ad_id if alias else ad_id

    return alias


# Импортируем актуальные маппинги из дампа БД
from mapper.db_mappings import CATEGORY_IDS, CITY_IDS, REGION_IDS

# ID страны (Россия)
COUNTRY_ID = 1

# Дополнительные алиасы для регионов (сокращенные названия -> полные в БД)
REGION_ALIASES = {
    "ДНР": "Донецкая область (ДНР)",
    "ЛНР": "Луганская Народная Республика (ЛНР)",
    "Запорожье": "Запорожская область",
    "Херсон": "Херсонская область",
}


def get_category_id(category1: str, category2: str) -> int:
    """Получить ID категории по названиям"""
    # Сначала пробуем подкатегорию
    if category2 and category2 in CATEGORY_IDS:
        return CATEGORY_IDS[category2]
    # Потом главную категорию
    if category1 and category1 in CATEGORY_IDS:
        return CATEGORY_IDS[category1]
    # По умолчанию - "Прочее" или 0
    return 0


def get_city_id(city_name: str) -> int:
    """Получить ID города по названию"""
    return CITY_IDS.get(city_name, 0)


def get_region_id(region_name: str) -> int:
    """Получить ID региона по названию"""
    # Сначала пробуем алиасы (ДНР -> Донецкая область (ДНР))
    full_name = REGION_ALIASES.get(region_name, region_name)
    return REGION_IDS.get(full_name, REGION_IDS.get(region_name, 0))


def ad_to_sql_insert(
    ad: Ad,
    category_id: int,
    city_id: int,
    region_id: int,
    user_id: int = 1,
    status: int = 1,
    publication_days: int = 30,
) -> str:
    """
    Генерировать INSERT-запрос для одного объявления

    Args:
        ad: Объявление
        category_id: ID категории в БД
        city_id: ID города в БД
        region_id: ID региона в БД
        user_id: ID пользователя-владельца (по умолчанию 1 = админ)
        status: Статус объявления (1 = активно, 2 = на модерации)
        publication_days: Срок публикации в днях (по умолчанию 30)

    Returns:
        SQL INSERT запрос
    """
    from datetime import timedelta

    # Вычисляем значения
    price = parse_price(ad.price)
    alias = generate_alias(ad.title, ad.id)

    # Дата добавления - всегда сегодня
    datetime_add = format_datetime_today()

    # Дата окончания публикации (+N дней от сегодня)
    period_end = datetime.now() + timedelta(days=publication_days)
    period_publication = f"'{period_end.strftime('%Y-%m-%d %H:%M:%S')}'"

    # Очищаем описание от телефонов с эмоджи и добавляем контакты в конец
    cleaned_description = clean_description(ad.description, ad.phone, ad.seller_name)

    # Изображения - в БД хранятся локальные имена файлов
    # Ограничиваем количество фото для категорий не недвижимость/авто
    limited_photos = limit_photos(ad.photos or [], category_id)
    images_json = photos_to_json(limited_photos)

    # Координаты
    lat = float(ad.lat) if ad.lat else 0.0
    lng = float(ad.lng) if ad.lng else 0.0

    # VIP из is_top
    vip = 1 if ad.is_top else 0

    # Фильтр-теги из params (формат: "ключ1;ключ2;значение")
    # В БД используется формат через точку с запятой, не JSON
    filter_tags_parts = []
    for key, val in ad.params.items():
        filter_tags_parts.append(f"{val}")
    filter_tags = escape_sql(';'.join(filter_tags_parts)) if filter_tags_parts else "''"

    # ID импорта для отслеживания дубликатов (уникальный ключ)
    import_id = f"dnr_red_{ad.id}"

    # Поисковые теги из заголовка и категории
    search_parts = []
    if ad.title:
        # Берём ключевые слова из заголовка
        words = ad.title.split()[:5]
        search_parts.extend(words)
    if ad.category:
        search_parts.append(ad.category)
    if ad.subcategory:
        search_parts.append(ad.subcategory)
    search_tags = escape_sql(';'.join(search_parts)[:255]) if search_parts else "''"

    # INSERT ... SELECT ... WHERE NOT EXISTS - проверка дубликатов без изменения структуры БД
    sql = f"""INSERT INTO `nulled_ads` (
    `ads_title`,
    `ads_alias`,
    `ads_text`,
    `ads_id_cat`,
    `ads_datetime_add`,
    `ads_datetime_view`,
    `ads_id_user`,
    `ads_images`,
    `ads_price`,
    `ads_address`,
    `ads_latitude`,
    `ads_longitude`,
    `ads_metro_ids`,
    `ads_period_publication`,
    `ads_city_id`,
    `ads_status`,
    `ads_region_id`,
    `ads_country_id`,
    `ads_note`,
    `ads_count_display`,
    `ads_currency`,
    `ads_period_day`,
    `ads_update`,
    `ads_sorting`,
    `ads_auction`,
    `ads_auction_duration`,
    `ads_auction_price_sell`,
    `ads_auction_day`,
    `ads_area_ids`,
    `ads_id_import`,
    `ads_import_images`,
    `ads_video`,
    `ads_vip`,
    `ads_auto_renewal`,
    `ads_online_view`,
    `ads_price_old`,
    `ads_filter_tags`,
    `ads_price_free`,
    `ads_available`,
    `ads_available_unlimitedly`,
    `ads_booking`,
    `ads_price_measure`,
    `ads_price_from`,
    `ads_booking_additional_services`,
    `ads_booking_prepayment_percent`,
    `ads_booking_max_guests`,
    `ads_booking_min_days`,
    `ads_booking_max_days`,
    `ads_booking_available`,
    `ads_booking_available_unlimitedly`,
    `ads_electron_product_links`,
    `ads_electron_product_text`,
    `ads_delivery_status`,
    `ads_delivery_weight`,
    `ads_map_lat`,
    `ads_map_lon`,
    `ads_search_tags`,
    `ads_count_view`,
    `ads_condition_status`
)
SELECT
    {escape_sql(ad.title)},
    {escape_sql(alias)},
    {escape_sql(cleaned_description)},
    {category_id},
    {datetime_add},
    NULL,
    {user_id},
    {images_json},
    {price},
    {escape_sql_or_empty(ad.address)},
    {escape_sql_or_empty(ad.lat)},
    {escape_sql_or_empty(ad.lng)},
    '',
    {period_publication},
    {city_id},
    {status},
    {region_id},
    {COUNTRY_ID},
    '',
    0,
    {escape_sql_or_empty(ad.currency)},
    {publication_days},
    NULL,
    0,
    0,
    NULL,
    0,
    1,
    '',
    {escape_sql(import_id)},
    {images_json},
    '',
    {vip},
    0,
    0,
    0,
    {filter_tags},
    {1 if price == 0 else 0},
    0,
    0,
    0,
    '',
    0,
    '',
    0,
    0,
    0,
    0,
    0,
    0,
    NULL,
    NULL,
    0,
    0,
    {lat},
    {lng},
    {search_tags},
    0,
    0
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM `nulled_ads` WHERE `ads_id_import` = {escape_sql(import_id)}
);"""

    return sql


def export_to_sql(
    ads: Sequence[Ad],
    filename: str,
    category_mapper: Optional[callable] = None,
    user_id: int = 1,
) -> int:
    """
    Экспортировать объявления в SQL-файл

    Args:
        ads: Список объявлений
        filename: Путь к выходному файлу
        category_mapper: Функция маппинга категорий (category, subcategory) -> (cat1, cat2)
        user_id: ID пользователя-владельца

    Returns:
        Количество экспортированных объявлений
    """
    from export.unisite_export import map_categories

    if category_mapper is None:
        category_mapper = map_categories

    lines = [
        "-- SQL Export from ads-parser",
        f"-- Generated: {datetime.now().isoformat()}",
        f"-- Total ads: {len(ads)}",
        "",
        "-- ============================================================",
        "-- ВАЖНО: Перед выполнением проверьте следующее:",
        "-- ============================================================",
        "-- 1. ID категорий и городов соответствуют целевой БД",
        "-- 2. Дубликаты проверяются по полю ads_id_import (dnr_red_XXXXX)",
        "--    Структура БД НЕ изменяется!",
        "-- 3. ИЗОБРАЖЕНИЯ: В полях ads_images/ads_import_images указаны URL.",
        "--    Платформа хранит локальные имена файлов, не URL!",
        "-- ============================================================",
        "",
        "SET NAMES utf8mb4;",
        "",
    ]

    count = 0
    for ad in ads:
        # Маппинг категорий
        cat1, cat2 = category_mapper(ad.category, ad.subcategory)
        category_id = get_category_id(cat1, cat2)

        # Маппинг географии
        city_id = get_city_id(ad.city) if ad.city else 0
        region_id = get_region_id(ad.region) if ad.region else 0

        sql = ad_to_sql_insert(
            ad,
            category_id=category_id,
            city_id=city_id,
            region_id=region_id,
            user_id=user_id,
        )

        lines.append(f"-- Ad ID: {ad.id} | {ad.title[:50] if ad.title else 'No title'}...")
        lines.append(sql)
        lines.append("")
        count += 1

    lines.extend([
        "SET FOREIGN_KEY_CHECKS = 1;",
        "",
        f"-- Export complete: {count} ads",
    ])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return count


def load_existing_import_ids(filename: str) -> set[str]:
    """
    Загрузить ID уже экспортированных объявлений из SQL-файла

    Args:
        filename: Путь к файлу

    Returns:
        Множество ID в формате dnr_red_XXXXX
    """
    import os
    if not os.path.exists(filename):
        return set()

    ids = set()
    pattern = re.compile(r"'dnr_red_(\d+)'")

    try:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    ids.add(match.group(1))
    except Exception:
        pass

    return ids
