"""Маппинг городов и регионов"""

# Город -> Регион
CITY_REGIONS = {
    # ДНР
    "donetsk": "ДНР",
    "makeyevka": "ДНР",
    "gorlovka": "ДНР",
    "mariupol": "ДНР",
    "yenakievo": "ДНР",
    "krasnoarmejsk": "ДНР",
    "dimitrov": "ДНР",
    "torez": "ДНР",
    "snezhnoe": "ДНР",
    "shahterskk": "ДНР",
    "khartsyzsk": "ДНР",
    "jasinovataja": "ДНР",
    "dokuchajevsk": "ДНР",
    "volnovaha": "ДНР",
    "zugres": "ДНР",
    "novoazovsk": "ДНР",
    "amvrosijevka": "ДНР",
    "debalcevo": "ДНР",
    "ilovajsk": "ДНР",
    "zhdanovka": "ДНР",
    "kirovskoje": "ДНР",
    "komsomolskoje": "ДНР",

    # ЛНР
    "lugansk": "ЛНР",
    "alchevsk": "ЛНР",
    "krasnyj-luch": "ЛНР",
    "severodonetsk": "ЛНР",
    "lisichansk": "ЛНР",
    "stahanov": "ЛНР",
    "rubezhnoe": "ЛНР",
    "sverdlovsk": "ЛНР",
    "krasnodon": "ЛНР",
    "bryanka": "ЛНР",
    "pervomaysk": "ЛНР",
    "rovenki": "ЛНР",

    # Запорожье
    "zaporozhe": "Запорожье",
    "melitopol": "Запорожье",
    "berdyansk": "Запорожье",
    "energodar": "Запорожье",
    "gulyaypole": "Запорожье",
    "orekhov": "Запорожье",

    # Херсон
    "kherson": "Херсон",
    "kakhovka": "Херсон",
    "skadovsk": "Херсон",
    "genichesk": "Херсон",
    "berislav": "Херсон",
    "golaya-pristan": "Херсон",
}

# Город slug -> Название
CITY_NAMES = {
    # ДНР
    "donetsk": "Донецк",
    "makeyevka": "Макеевка",
    "gorlovka": "Горловка",
    "mariupol": "Мариуполь",
    "yenakievo": "Енакиево",
    "krasnoarmejsk": "Красноармейск",
    "dimitrov": "Димитров",
    "torez": "Торез",
    "snezhnoe": "Снежное",
    "shahterskk": "Шахтёрск",
    "khartsyzsk": "Харцызск",
    "jasinovataja": "Ясиноватая",
    "dokuchajevsk": "Докучаевск",
    "volnovaha": "Волноваха",
    "zugres": "Зугрэс",
    "novoazovsk": "Новоазовск",
    "amvrosijevka": "Амвросиевка",
    "debalcevo": "Дебальцево",
    "ilovajsk": "Иловайск",
    "zhdanovka": "Ждановка",
    "kirovskoje": "Кировское",
    "komsomolskoje": "Комсомольское",

    # ЛНР
    "lugansk": "Луганск",
    "alchevsk": "Алчевск",
    "krasnyj-luch": "Красный Луч",
    "severodonetsk": "Северодонецк",
    "lisichansk": "Лисичанск",
    "stahanov": "Стаханов",
    "rubezhnoe": "Рубежное",
    "sverdlovsk": "Свердловск",
    "krasnodon": "Краснодон",
    "bryanka": "Брянка",
    "pervomaysk": "Первомайск",
    "rovenki": "Ровеньки",

    # Запорожье
    "zaporozhe": "Запорожье",
    "melitopol": "Мелитополь",
    "berdyansk": "Бердянск",
    "energodar": "Энергодар",
    "gulyaypole": "Гуляйполе",
    "orekhov": "Орехов",

    # Херсон
    "kherson": "Херсон",
    "kakhovka": "Каховка",
    "skadovsk": "Скадовск",
    "genichesk": "Геническ",
    "berislav": "Берислав",
    "golaya-pristan": "Голая Пристань",
}


def get_city_region(city_slug: str) -> str:
    """Получить регион по slug города"""
    return CITY_REGIONS.get(city_slug, "")


def get_city_name(city_slug: str) -> str:
    """Получить название города по slug"""
    return CITY_NAMES.get(city_slug, city_slug)
