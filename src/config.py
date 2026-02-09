"""Конфигурация парсера dnr.red"""

BASE_URL = "https://dnr.red"

# Rate limiting
REQUEST_DELAY = 1.0  # секунд между запросами
REQUEST_TIMEOUT = 30  # таймаут запроса

# Retry настройки
MAX_RETRIES = 3
RETRY_DELAY = 2  # секунд

# User-Agent для запросов
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Максимум страниц пагинации
MAX_PAGES = 1000

# Категории
CATEGORIES = [
    "vzaimopomoshh",
    "nedvizhimost",
    "auto",
    "detskiy-mir",
    "elektronika",
    "zhivotnye",
    "uslugi",
    "moda-i-stil",
    "dom-i-sad",
    "biznes",
    "rabota",
    "hobbi-otdyh-i-sport",
]

# Города по регионам
CITIES = {
    "ДНР": [
        "donetsk",
        "makeyevka",
        "gorlovka",
        "mariupol",
        "yenakievo",
        "krasnoarmejsk",
        "dimitrov",
        "torez",
        "snezhnoe",
        "shahterskk",
        "khartsyzsk",
        "jasinovataja",
        "dokuchajevsk",
        "volnovaha",
        "zugres",
        "novoazovsk",
        "amvrosijevka",
        "debalcevo",
        "ilovajsk",
        "zhdanovka",
        "kirovskoje",
        "komsomolskoje",
    ],
    "ЛНР": [
        "lugansk",
        "alchevsk",
        "krasnyj-luch",
        "severodonetsk",
        "lisichansk",
        "stahanov",
        "rubezhnoe",
        "sverdlovsk",
        "krasnodon",
        "bryanka",
        "pervomaysk",
        "rovenki",
    ],
    "Запорожье": [
        "zaporozhe",
        "melitopol",
        "berdyansk",
        "energodar",
        "gulyaypole",
        "orekhov",
    ],
    "Херсон": [
        "kherson",
        "kakhovka",
        "skadovsk",
        "genichesk",
        "berislav",
        "golaya-pristan",
    ],
}

# Выходной файл
OUTPUT_FILE = "ads.csv"
IMAGES_DIR = "images"
