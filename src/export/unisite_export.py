"""Экспорт объявлений в формат UniSite"""

import csv
import re
from typing import Sequence

from models import Ad


# Полный маппинг подкатегории -> (Категория1, Категория2) для dnrbuy.ru
# Ключи - точные названия после .replace("-", " ").title() из URL dnr.red
SUBCATEGORY_TO_CATEGORIES = {
    # ===== ВЗАИМОПОМОЩЬ (vzaimopomoshh) =====
    "Dla Detej": ("Услуги", "Прочие услуги"),
    "Drugoje": ("Услуги", "Прочие услуги"),
    "Jeda Produkty": ("Услуги", "Прочие услуги"),
    "Lekarstva I Gigijenicheskije Sredstva": ("Услуги", "Медицинские услуги"),
    "Medicinskaja Pomoshh": ("Услуги", "Медицинские услуги"),
    "Odezhda I Obuv": ("Услуги", "Прочие услуги"),
    "Transport": ("Услуги", "Перевозки"),
    "Zhilje": ("Услуги", "Прочие услуги"),

    # ===== НЕДВИЖИМОСТЬ (nedvizhimost) =====
    "Arenda Nedvizhimosti": ("Недвижимость", "Аренда квартиры длительно"),
    "Prodazha Nedvizhimosti": ("Недвижимость", "Продажа квартиры"),
    "Kommercheskaja Nedvizhimost": ("Недвижимость", "Коммерческая недвижимость"),
    "Nedvizhimost Za Rubezhom": ("Недвижимость", "Недвижимость за рубежом"),
    "Ischu Kompanona": ("Недвижимость", "Прочая недвижимость"),
    "Obmen Nedvizhimosti": ("Недвижимость", "Обмен недвижимости"),
    # Фолбэки для старых названий из subcat_names в detail.py
    "Продажа": ("Недвижимость", "Продажа квартиры"),
    "Аренда": ("Недвижимость", "Аренда квартиры длительно"),
    "Аренда квартир": ("Недвижимость", "Аренда квартиры длительно"),
    "Коммерческая": ("Недвижимость", "Коммерческая недвижимость"),
    "Квартиры": ("Недвижимость", "Продажа квартиры"),
    "За рубежом": ("Недвижимость", "Недвижимость за рубежом"),

    # ===== АВТО (auto) -> ТРАНСПОРТ =====
    "Legkovye Avtomobili": ("Транспорт", "Легковые автомобили"),
    "Moto": ("Транспорт", "Мототехника"),
    "Spetstehnika": ("Транспорт", "Спецтехника"),
    "Selhoztehnika": ("Транспорт", "Сельхозтехника"),
    "Vozdushnyy Transport": ("Транспорт", "Воздушный транспорт"),
    "Zapchasti Aksessuary": ("Транспорт", "Запчасти и аксессуары"),
    "Avto Moto Uslugi": ("Услуги", "Автоуслуги"),
    "Kommercheskiy Gruzovoy": ("Транспорт", "Грузовой транспорт"),
    "Drugoy Transport": ("Транспорт", "Другой транспорт"),

    # ===== ДЕТСКИЙ МИР (detskiy-mir) -> ДЕТСКИЕ ТОВАРЫ =====
    "Detskaya Odezhda": ("Детские товары", "Детская одежда"),
    "Detskaya Obuv": ("Детские товары", "Детская обувь"),
    "Detskie Kolyaski": ("Детские товары", "Детские коляски"),
    "Detskie Avtokresla": ("Детские товары", "Детские автокресла"),
    "Detskaya Mebel": ("Детские товары", "Детская мебель"),
    "Igrushki": ("Детские товары", "Игрушки"),
    "Detskiy Transport": ("Детские товары", "Детский транспорт"),
    "Kormlenie": ("Детские товары", "Товары для кормления"),
    "Tovary Dlya Shkolnikov": ("Детские товары", "Товары для школьников"),
    "Prochie Detskie Tovary": ("Детские товары", "Прочие детские товары"),

    # ===== ЭЛЕКТРОНИКА (elektronika) =====
    "Telefony": ("Электроника", "Телефоны"),
    "Kompyutery": ("Электроника", "Компьютеры"),
    "Foto Video": ("Электроника", "Фото и видеокамеры"),
    "Tv Videotehnika": ("Электроника", "ТВ и видеотехника"),
    "Audiotehnika": ("Электроника", "Аудиотехника"),
    "Igry I Igrovye Pristavki": ("Электроника", "Игровые приставки"),
    "Tehnika Dlya Doma": ("Для дома и дачи", "Бытовая техника"),
    "Tehnika Dlya Kuhni": ("Для дома и дачи", "Техника для кухни"),
    "Klimaticheskoe Oborudovanie": ("Для дома и дачи", "Климатическое оборудование"),
    "Individualnyy Uhod": ("Красота и здоровье", "Приборы для ухода"),
    "Aksessuary I Komplektuyuschie": ("Электроника", "Комплектующие"),
    "Planshety El Knigi I Aksessuary": ("Электроника", "Планшеты"),
    "Prochaja Elektronika": ("Электроника", "Прочая электроника"),

    # ===== ЖИВОТНЫЕ (zhivotnye) =====
    "Sobaki": ("Животные", "Собаки"),
    "Koshki": ("Животные", "Кошки"),
    "Akvariumnye Rybki": ("Животные", "Аквариумистика"),
    "Ptitsy": ("Животные", "Птицы"),
    "Gryzuny": ("Животные", "Грызуны"),
    "Reptilii": ("Животные", "Другие животные"),
    "Selskohozyaystvennye Zhivotnye": ("Животные", "Сельхоз животные"),
    "Tovary Dlya Zhivotnyh": ("Животные", "Товары для животных"),
    "Vyazka": ("Животные", "Вязка"),
    "Drugie Zhivotnye": ("Животные", "Другие животные"),
    "Besplatno Zhivotnyje I Vazka": ("Животные", "Отдам даром"),

    # ===== УСЛУГИ (uslugi) =====
    "Stroitelstvo Otdelka Remont": ("Услуги", "Строительство и ремонт"),
    "Perevozki Arenda Transporta": ("Услуги", "Грузоперевозки"),
    "Nyani Sidelki": ("Услуги", "Няни и сиделки"),
    "Krasota Zdorove": ("Красота и здоровье", "Салоны красоты"),
    "Obrazovanie": ("Услуги", "Обучение и курсы"),
    "Uslugi Dlya Zhivotnyh": ("Услуги", "Услуги для животных"),
    "Razvlechenie Foto Video": ("Услуги", "Фото и видеосъемка"),
    "Turizm Immigratsiya": ("Услуги", "Туризм"),
    "Uslugi Perevodchikov Nabor Teksta": ("Услуги", "Переводы"),
    "Obsluzhivanie Remont Tehniki": ("Услуги", "Ремонт техники"),
    "Sport": ("Услуги", "Спортивные услуги"),
    "Yuridicheskie Uslugi": ("Услуги", "Юридические услуги"),
    "Bezopasnost Detektivy Rozysk": ("Услуги", "Охрана и безопасность"),
    "Prokat Tovarov": ("Услуги", "Прокат"),
    "Prochie Uslugi": ("Услуги", "Прочие услуги"),

    # ===== МОДА И СТИЛЬ (moda-i-stil) =====
    "Odezhda": ("Мода и стиль", "Одежда"),
    "Dlya Svadby": ("Мода и стиль", "Свадебные товары"),
    "Naruchnye Chasy": ("Мода и стиль", "Часы"),
    "Aksessuary": ("Мода и стиль", "Аксессуары"),
    "Podarki": ("Мода и стиль", "Подарки"),
    "Specodezhda Specobuv I Aksessuary": ("Мода и стиль", "Спецодежда"),
    "Moda Raznoje": ("Мода и стиль", "Прочее"),

    # ===== ДОМ И САД (dom-i-sad) -> ДЛЯ ДОМА И ДАЧИ / СТРОЙМАТЕРИАЛЫ =====
    "Mebel": ("Для дома и дачи", "Мебель"),
    "Predmety Interera": ("Для дома и дачи", "Предметы интерьера"),
    "Stroitelstvo Remont": ("Стройматериалы и инструменты", "Стройматериалы"),
    "Instrumenty": ("Стройматериалы и инструменты", "Инструменты"),
    "Komnatnye Rasteniya": ("Для дома и дачи", "Растения"),
    "Sadovye Rasteniya": ("Для дома и дачи", "Растения"),
    "Rassada": ("Для дома и дачи", "Растения"),
    "Sadovyy Inventar": ("Для дома и дачи", "Садовый инвентарь"),
    "Sadovodstvo Prochee": ("Для дома и дачи", "Сад и огород"),
    "Hozyaystvennyy Inventar": ("Для дома и дачи", "Хозтовары"),
    "Prochie Tovary Dlya Doma": ("Для дома и дачи", "Прочее для дома"),
    "Produkty Pitanija Napitki": ("Для дома и дачи", "Продукты питания"),
    "Posuda Kuhonnaja Utvar": ("Для дома и дачи", "Посуда"),

    # ===== БИЗНЕС (biznes) -> ДЛЯ БИЗНЕСА =====
    "Tovary": ("Для Бизнеса", "Товары для бизнеса"),
    "Vse Dlya Ofisa": ("Для Бизнеса", "Всё для офиса"),
    "Syre Materialy": ("Для Бизнеса", "Сырьё и материалы"),
    "Oborudovanie": ("Для Бизнеса", "Оборудование"),
    "Prodazha Biznesa": ("Для Бизнеса", "Готовый бизнес"),
    "Uslugi Dlya Biznesa": ("Для Бизнеса", "Услуги для бизнеса"),
    "Procheje": ("Для Бизнеса", "Прочее"),

    # ===== РАБОТА (rabota) -> ВАКАНСИИ =====
    "Roznichnaya Torgovlya Prodazhi": ("Вакансии", "Торговля и продажи"),
    "Transport Logistika": ("Вакансии", "Транспорт и логистика"),
    "Stroitelstvo": ("Вакансии", "Строительство"),
    "Bary Restorany Razvlecheniya": ("Вакансии", "Рестораны и кафе"),
    "Yurisprudentsiya I Buhgalteriya": ("Вакансии", "Юриспруденция"),
    "Ohrana Bezopasnost": ("Вакансии", "Охрана"),
    "Domashniy Personal": ("Вакансии", "Домашний персонал"),
    "Krasota Fitnes Sport": ("Вакансии", "Красота и спорт"),
    "Kultura Iskusstvo": ("Вакансии", "Культура и искусство"),
    "Meditsina Farmatsiya": ("Вакансии", "Медицина"),
    "It Telekom Kompyutery": ("Вакансии", "IT и телеком"),
    "Nedvizhimost": ("Вакансии", "Недвижимость"),
    "Marketing Reklama Dizayn": ("Вакансии", "Маркетинг и реклама"),
    "Proizvodstvo Energetika": ("Вакансии", "Производство"),
    "Cekretariat Aho": ("Вакансии", "Секретариат"),
    "Nachalo Karery Studenty": ("Вакансии", "Начало карьеры"),
    "Servis I Byt": ("Вакансии", "Сервис и быт"),
    "Drugie Sfery Zanyatiy": ("Вакансии", "Другие сферы"),
    "Banki Finansy Strahovanije": ("Вакансии", "Финансы"),

    # ===== ХОББИ, ОТДЫХ И СПОРТ (hobbi-otdyh-i-sport) -> ХОББИ / СПОРТ =====
    "Antikvariat Kollektsii": ("Хобби и развлечения", "Коллекционирование"),
    "Muzykalnye Instrumenty": ("Хобби и развлечения", "Музыкальные инструменты"),
    "Sport Otdyh": ("Спорт и отдых", "Спорттовары"),
    "Knigi Zhurnaly": ("Хобби и развлечения", "Книги и журналы"),
    "Cd Dvd Plastinki": ("Хобби и развлечения", "CD/DVD/Пластинки"),
    "Bilety": ("Хобби и развлечения", "Билеты"),
    "Poisk Grupp Muzykantov": ("Хобби и развлечения", "Музыканты"),
    "Tovary Dla Tvorchestva": ("Хэндмейд", "Товары для творчества"),
    "Tovary Dla Rukodelija": ("Хэндмейд", "Рукоделие"),
}

# Фолбэк маппинг категорий (если подкатегория не найдена)
CATEGORY_FALLBACK = {
    "Недвижимость": "Недвижимость",
    "Авто": "Транспорт",
    "Мода и стиль": "Мода и стиль",
    "Детский мир": "Детские товары",
    "Хобби, отдых и спорт": "Хобби и развлечения",
    "Дом и сад": "Для дома и дачи",
    "Электроника": "Электроника",
    "Услуги": "Услуги",
    "Животные": "Животные",
    "Работа": "Вакансии",
    "Бизнес": "Для Бизнеса",
    "Взаимопомощь": "Услуги",
}


def map_categories(category: str, subcategory: str) -> tuple[str, str]:
    """
    Определить Категорию1 и Категорию2 на основе подкатегории

    Args:
        category: Исходная категория с dnr.red
        subcategory: Исходная подкатегория с dnr.red

    Returns:
        (Категория1, Категория2) для dnrbuy.ru
    """
    # Сначала пробуем найти по подкатегории
    if subcategory and subcategory in SUBCATEGORY_TO_CATEGORIES:
        return SUBCATEGORY_TO_CATEGORIES[subcategory]

    # Фолбэк - используем маппинг категорий
    cat1 = CATEGORY_FALLBACK.get(category, category) if category else ""
    cat2 = subcategory or ""

    return cat1, cat2


# Маппинг параметров dnr.red -> UniSite
PARAMS_MAP = {
    # Недвижимость
    "Этажность дома": "Этажей в доме",
    "Этаж": "Этаж",
    "Количество комнат": "Комнат",
    "Общая площадь": "Площадь дома",
    "Площадь": "Площадь дома",
    "Жилая площадь": "Жилая площадь",
    "Площадь кухни": "Площадь кухни",
    "Тип дома": "Материал стен",
    "Состояние квартиры": "Состояние",
    "Площадь участка": "Площадь участка",
    # Авто
    "Год выпуска": "Год выпуска",
    "Пробег": "Пробег",
    "Коробка передач": "Коробка передач",
    "Тип кузова": "Тип кузова",
    "Объём двигателя": "Объем двигателя",
    "Вид топлива": "Топливо",
    "Мощность": "Мощность",
    "Цвет": "Цвет",
    "Состояние машины": "Состояние",
    "Модель": "Модель",
}


def normalize_param_value(key: str, value: str) -> str:
    """Нормализовать значение параметра"""
    # Убираем единицы измерения для числовых значений
    if key in ("Площадь дома", "Жилая площадь", "Площадь кухни", "Площадь участка"):
        # "36 м2" -> "36"
        match = re.match(r'([\d.]+)', value)
        if match:
            return match.group(1)
    if key == "Пробег":
        # "300000 км" -> "300000"
        match = re.match(r'([\d]+)', value)
        if match:
            return match.group(1)
    if key == "Объем двигателя":
        # "1.6 см3" -> "1.6"
        match = re.match(r'([\d.]+)', value)
        if match:
            return match.group(1)
    return value


UNISITE_FIELDS = [
    "Название",
    "Цена",
    "Дата",
    "Телефон",
    "Контактное лицо (автор объявления)",
    "Тип автора",
    "Регион",
    "Город",
    "Адрес",
    "Описание",
    "Категория1",
    "Категория2",
    "ID на сайте",
    "Источник",
    "lat",
    "lng",
    "Доп.параметры",
    "URL",
    "Ссылки на картинки",
]


def ad_to_unisite(ad: Ad) -> dict:
    """Конвертировать объявление в формат UniSite"""

    # Дата в формате dd.mm.yyyy HH:MM
    date_str = ad.date or ""
    if date_str and " " not in date_str:
        date_str = f"{date_str} 00:00"

    # Фото через запятую
    photos_str = ",".join(ad.photos) if ad.photos else ""

    # Доп. параметры
    params = []
    if ad.is_top:
        params.append("Тип объявления=Топ")
    if ad.district:
        params.append(f"Район={ad.district}")
    # Добавляем параметры из объявления с маппингом
    for key, val in ad.params.items():
        # Применяем маппинг имени параметра
        mapped_key = PARAMS_MAP.get(key, key)
        # Нормализуем значение
        mapped_val = normalize_param_value(mapped_key, val)
        params.append(f"{mapped_key}={mapped_val}")
    params_str = "|".join(params)

    return {
        "Название": ad.title,
        "Цена": ad.price or "",
        "Дата": date_str,
        "Телефон": ad.phone or "",
        "Контактное лицо (автор объявления)": ad.seller_name or "",
        "Тип автора": "Частное лицо",
        "Регион": ad.region or "",
        "Город": ad.city or "",
        "Адрес": ad.address or "",
        "Описание": ad.description,
        "Категория1": map_categories(ad.category, ad.subcategory)[0],
        "Категория2": map_categories(ad.category, ad.subcategory)[1],
        "ID на сайте": ad.id,
        "Источник": "dnr.red",
        "lat": ad.lat or "",
        "lng": ad.lng or "",
        "Доп.параметры": params_str,
        "URL": ad.url,
        "Ссылки на картинки": photos_str,
    }


def load_existing_ids_unisite(filename: str) -> set[str]:
    """
    Загрузить ID существующих объявлений из файла UniSite

    Args:
        filename: Путь к файлу

    Returns:
        Множество ID
    """
    import os
    if not os.path.exists(filename):
        return set()

    ids = set()
    try:
        with open(filename, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                ad_id = row.get("ID на сайте", "")
                if ad_id:
                    ids.add(ad_id)
    except Exception:
        pass
    return ids


def export_to_unisite(ads: Sequence[Ad], filename: str, append: bool = False) -> int:
    """
    Экспортировать объявления в формат UniSite

    Args:
        ads: Список объявлений
        filename: Путь к файлу
        append: Если True - дозаписывать новые объявления

    Returns:
        Количество записанных объявлений
    """
    import os

    # Если режим дозаписи - загружаем существующие ID
    existing_ids = set()
    file_exists = os.path.exists(filename)

    if append and file_exists:
        existing_ids = load_existing_ids_unisite(filename)
        # Фильтруем только новые объявления
        new_ads = [ad for ad in ads if ad.id not in existing_ids]
        if not new_ads:
            return 0  # Нет новых объявлений

        # Дозаписываем без заголовка
        with open(filename, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=UNISITE_FIELDS,
                delimiter=";",
                quoting=csv.QUOTE_MINIMAL,
            )
            for ad in new_ads:
                writer.writerow(ad_to_unisite(ad))
        return len(new_ads)

    # Обычный режим - перезаписываем файл
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=UNISITE_FIELDS,
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()

        for ad in ads:
            writer.writerow(ad_to_unisite(ad))

    return len(ads)
