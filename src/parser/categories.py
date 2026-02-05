"""Парсер категорий, подкатегорий и районов"""

import re
import time
import requests
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

from config import BASE_URL


# Кэш категорий (статичны для всех городов)
CATEGORIES = {
    'auto': ['vozdushnyy-transport', 'obmen-transporta', 'zapchasti-aksessuary', 'vodnyy-auto',
             'avto-moto-uslugi', 'ochered-na-mashinu', 'kommercheskiy-gruzovoy', 'legkovye-avtomobili',
             'spetstehnika', 'vodnyy-transport', 'drugoy-transport', 'moto', 'selhoztehnika'],
    'biznes': ['prodazha-biznesa', 'syre-materialy', 'tovary', 'oborudovanie', 'vse-dlya-ofisa',
               'uslugi-dlya-biznesa', 'procheje'],
    'detskiy-mir': ['detskiy-transport', 'prochie-detskie-tovary', 'igrushki', 'detskaya-mebel',
                    'detskaya-odezhda', 'tovary-dlya-shkolnikov', 'detskie-kolyaski', 'kormlenie',
                    'detskaya-obuv', 'detskie-avtokresla'],
    'dom-i-sad': ['sadovye-rasteniya', 'produkty-pitanija-napitki', 'predmety-interera', 'rassada',
                  'sadovyy-inventar', 'prochie-tovary-dlya-doma', 'instrumenty', 'mebel',
                  'sadovodstvo-prochee', 'posuda-kuhonnaja-utvar', 'hozyaystvennyy-inventar',
                  'komnatnye-rasteniya', 'stroitelstvo-remont'],
    'elektronika': ['prochaja-elektronika', 'tv-videotehnika', 'klimaticheskoe-oborudovanie',
                    'tehnika-dlya-kuhni', 'planshety-el-knigi-i-aksessuary', 'individualnyy-uhod',
                    'aksessuary-i-komplektuyuschie', 'igry-i-igrovye-pristavki', 'tehnika-dlya-doma',
                    'kompyutery', 'audiotehnika', 'foto-video', 'telefony'],
    'hobbi-otdyh-i-sport': ['knigi-zhurnaly', 'poisk-grupp-muzykantov', 'drugoje', 'cd-dvd-plastinki',
                            'sport-otdyh', 'tovary-dla-rukodelija', 'tovary-dla-tvorchestva',
                            'muzykalnye-instrumenty', 'bilety', 'antikvariat-kollektsii'],
    'moda-i-stil': ['aksessuary', 'moda-raznoje', 'krasota-zdorove', 'dlya-svadby',
                    'specodezhda-specobuv-i-aksessuary', 'podarki', 'naruchnye-chasy', 'odezhda'],
    'nedvizhimost': ['arenda-nedvizhimosti', 'prodazha-nedvizhimosti', 'obmen-nedvizhimosti',
                     'nedvizhimost-za-rubezhom', 'kommercheskaja-nedvizhimost', 'ischu-kompanona'],
    'rabota': ['vakansii', 'rezyume'],
    'uslugi': ['prokat-tovarov', 'stroitelstvo-otdelka-remont', 'prochie-uslugi', 'turizm-immigratsiya',
               'uslugi-perevodchikov-nabor-teksta', 'obsluzhivanie-remont-tehniki', 'sport',
               'krasota-zdorove', 'obrazovanie', 'razvlechenie-foto-video', 'bezopasnost-detektivy-rozysk',
               'perevozki-arenda-transporta', 'uslugi-dlya-zhivotnyh', 'nyani-sidelki', 'yuridicheskie-uslugi'],
    'vzaimopomoshh': ['drugoje', 'dla-detej', 'jeda-produkty', 'lekarstva-i-gigijenicheskije-sredstva',
                      'medicinskaja-pomoshh', 'transport', 'zhilje', 'odezhda-i-obuv'],
    'zhivotnye': ['drugie-zhivotnye', 'selskohozyaystvennye-zhivotnye', 'akvariumnye-rybki', 'gryzuny',
                  'koshki', 'ptitsy', 'reptilii', 'vyazka', 'sobaki', 'tovary-dlya-zhivotnyh',
                  'besplatno-zhivotnyje-i-vazka'],
}


def get_categories() -> Dict[str, List[str]]:
    """Получить словарь категорий и подкатегорий"""
    return CATEGORIES


def get_all_category_paths() -> List[tuple]:
    """
    Получить все пути категорий для парсинга

    Returns:
        Список кортежей (category, subcategory)
    """
    paths = []
    for cat, subcats in CATEGORIES.items():
        if subcats:
            for subcat in subcats:
                paths.append((cat, subcat))
        else:
            paths.append((cat, None))
    return paths


def fetch_districts(city: str, category: str = 'nedvizhimost',
                   subcategory: str = 'arenda-nedvizhimosti') -> Dict[int, str]:
    """
    Получить список районов города с сайта

    Args:
        city: slug города
        category: категория для страницы поиска
        subcategory: подкатегория для страницы поиска

    Returns:
        Словарь {id: название}
    """
    url = f"{BASE_URL}/{city}/search/{category}/{subcategory}/"

    try:
        resp = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'lxml')
        districts = {}

        for inp in soup.select('input[name="rd[]"]'):
            value = inp.get('value')
            if not value or not value.isdigit():
                continue

            district_id = int(value)

            # Ищем label
            label = inp.find_next('label')
            if label:
                name = label.get_text(strip=True)
            else:
                parent = inp.parent
                name = parent.get_text(strip=True) if parent else f'Район {district_id}'

            # Пропускаем "Не важно"
            if 'не важно' not in name.lower():
                districts[district_id] = name

        return districts

    except Exception as e:
        print(f"Ошибка получения районов для {city}: {e}")
        return {}


# Кэш районов по городам
_districts_cache: Dict[str, Dict[int, str]] = {}


def get_districts(city: str) -> Dict[int, str]:
    """
    Получить районы города (с кэшированием)

    Args:
        city: slug города

    Returns:
        Словарь {id: название}
    """
    if city not in _districts_cache:
        _districts_cache[city] = fetch_districts(city)
    return _districts_cache[city]


def get_district_ids(city: str) -> List[int]:
    """Получить список ID районов города"""
    return list(get_districts(city).keys())


# Известные районы крупных городов (для оффлайн режима)
KNOWN_DISTRICTS = {
    'donetsk': {
        76: 'Будённовский',
        77: 'Ворошиловский',
        78: 'Калининский',
        79: 'Киевский',
        80: 'Кировский',
        81: 'Куйбышевский',
        82: 'Ленинский',
        83: 'Петровский',
        84: 'Пролетарский',
    },
    'lugansk': {
        86: 'Артёмовский',
        87: 'Жовтневый',
        88: 'Каменнобродский',
        89: 'Ленинский',
    },
    'mariupol': {
        90: 'Жовтневый',
        91: 'Ильичёвский',
        92: 'Орджоникидзевский',
        93: 'Приморский',
    },
}


def get_known_districts(city: str) -> Dict[int, str]:
    """Получить известные районы города без запроса"""
    return KNOWN_DISTRICTS.get(city, {})
