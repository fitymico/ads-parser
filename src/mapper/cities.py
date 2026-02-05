"""Маппинг городов и регионов"""

# Город -> Регион
CITY_REGIONS = {
    # ДНР
    "donetsk": "ДНР",
    "makeyevka": "ДНР",
    "gorlovka": "ДНР",
    "mariupol": "ДНР",
    "yenakievo": "ДНР",
    "kramatorsk": "ДНР",
    "slavyansk": "ДНР",
    "konstantinovka": "ДНР",
    "druzhkovka": "ДНР",
    "krasnoarmeysk": "ДНР",
    "dimitrov": "ДНР",
    "torez": "ДНР",
    "snezhnoe": "ДНР",
    "shahtersk": "ДНР",
    "khartsyzsk": "ДНР",
    "yasinovataya": "ДНР",
    "avdeevka": "ДНР",
    "dokuchaevsk": "ДНР",
    "volnovaha": "ДНР",

    # ЛНР
    "lugansk": "ЛНР",
    "alchevsk": "ЛНР",
    "krasnyy-luch": "ЛНР",
    "severodonetsk": "ЛНР",
    "lisichansk": "ЛНР",
    "stahanov": "ЛНР",
    "kommunarsk": "ЛНР",
    "rubezhnoye": "ЛНР",
    "sverdlovsk": "ЛНР",
    "krasnodon": "ЛНР",
    "bryanka": "ЛНР",
    "pervomaysk": "ЛНР",
    "rovenki": "ЛНР",
    "molodogvardeysk": "ЛНР",

    # Запорожье
    "zaporozhe": "Запорожье",
    "melitopol": "Запорожье",
    "berdyansk": "Запорожье",
    "energodar": "Запорожье",
    "tokmak": "Запорожье",
    "vasilievka": "Запорожье",
    "primorsk": "Запорожье",
    "gulyaypole": "Запорожье",
    "pologi": "Запорожье",
    "orehov": "Запорожье",

    # Херсон
    "kherson": "Херсон",
    "kakhovka": "Херсон",
    "skadovsk": "Херсон",
    "genichesk": "Херсон",
    "novaya-kahovka": "Херсон",
    "berislav": "Херсон",
    "golaya-pristan": "Херсон",
    "chjornobayevka": "Херсон",
}

# Город slug -> Название
CITY_NAMES = {
    # ДНР
    "donetsk": "Донецк",
    "makeyevka": "Макеевка",
    "gorlovka": "Горловка",
    "mariupol": "Мариуполь",
    "yenakievo": "Енакиево",
    "kramatorsk": "Краматорск",
    "slavyansk": "Славянск",
    "konstantinovka": "Константиновка",
    "druzhkovka": "Дружковка",
    "krasnoarmeysk": "Красноармейск",
    "dimitrov": "Димитров",
    "torez": "Торез",
    "snezhnoe": "Снежное",
    "shahtersk": "Шахтёрск",
    "khartsyzsk": "Харцызск",
    "yasinovataya": "Ясиноватая",
    "avdeevka": "Авдеевка",
    "dokuchaevsk": "Докучаевск",
    "volnovaha": "Волноваха",

    # ЛНР
    "lugansk": "Луганск",
    "alchevsk": "Алчевск",
    "krasnyy-luch": "Красный Луч",
    "severodonetsk": "Северодонецк",
    "lisichansk": "Лисичанск",
    "stahanov": "Стаханов",
    "kommunarsk": "Коммунарск",
    "rubezhnoye": "Рубежное",
    "sverdlovsk": "Свердловск",
    "krasnodon": "Краснодон",
    "bryanka": "Брянка",
    "pervomaysk": "Первомайск",
    "rovenki": "Ровеньки",
    "molodogvardeysk": "Молодогвардейск",

    # Запорожье
    "zaporozhe": "Запорожье",
    "melitopol": "Мелитополь",
    "berdyansk": "Бердянск",
    "energodar": "Энергодар",
    "tokmak": "Токмак",
    "vasilievka": "Васильевка",
    "primorsk": "Приморск",
    "gulyaypole": "Гуляйполе",
    "pologi": "Пологи",
    "orehov": "Орехов",

    # Херсон
    "kherson": "Херсон",
    "kakhovka": "Каховка",
    "skadovsk": "Скадовск",
    "genichesk": "Геническ",
    "novaya-kahovka": "Новая Каховка",
    "berislav": "Берислав",
    "golaya-pristan": "Голая Пристань",
    "chjornobayevka": "Чёрнобаевка",
}


def get_city_region(city_slug: str) -> str:
    """Получить регион по slug города"""
    return CITY_REGIONS.get(city_slug, "")


def get_city_name(city_slug: str) -> str:
    """Получить название города по slug"""
    return CITY_NAMES.get(city_slug, city_slug)
