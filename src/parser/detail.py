"""Парсер страницы объявления"""

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import BASE_URL
from models import Ad
from parser.client import HttpClient


class DetailParser:
    """Парсер детальной страницы объявления"""

    def __init__(self, client: HttpClient):
        self.client = client

    def _extract_id(self, url: str) -> str:
        """Извлечь ID из URL"""
        # Паттерн: {title}-{id}.html где ID - число 5+ цифр
        match = re.search(r'-(\d{5,})\.html$', url)
        return match.group(1) if match else ""

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлечь заголовок"""
        h1 = soup.select_one("h1")
        if h1:
            return h1.get_text(strip=True)
        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Извлечь описание"""
        # Селекторы для описания на dnr.red
        selectors = [
            ".l-item-description",
            ".item-description",
            ".description",
            "[itemprop='description']",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if len(text) > 10:
                    return text

        # Ищем по классу содержащему "descr"
        for elem in soup.find_all(class_=re.compile(r'descr', re.I)):
            text = elem.get_text(strip=True)
            if len(text) > 20:
                return text

        return ""

    def _extract_price(self, soup: BeautifulSoup) -> tuple[Optional[str], str]:
        """Извлечь цену и валюту"""
        # Селекторы для цены на dnr.red
        price_selectors = [
            ".vw-price-num",  # Основная цена объявления
            ".vw-price-box",
            ".vw-top-sticky-nav-info-price",
        ]

        for selector in price_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True).replace('\xa0', ' ')
                # Извлекаем числа
                match = re.search(r'(\d[\d\s]+)', text)
                if match:
                    price = match.group(1).replace(" ", "").strip()
                    if price.isdigit() and 1 <= len(price) <= 10:
                        currency = "RUB"
                        if "$" in text:
                            currency = "USD"
                        elif "€" in text:
                            currency = "EUR"
                        return price, currency

        return None, "RUB"

    def _extract_photos(self, soup: BeautifulSoup, ad_id: str) -> list[str]:
        """Извлечь URL фотографий для конкретного объявления"""
        photos = []

        # Ищем изображения, фильтруя по ID объявления
        # Формат URL: /items/{id_prefix}/{id}v{hash}.jpg
        id_prefix = ad_id[:4] if len(ad_id) >= 4 else ad_id

        def is_own_photo(src: str) -> bool:
            """Проверить, принадлежит ли фото этому объявлению"""
            if not src:
                return False
            # Фото принадлежит объявлению если содержит его ID
            return f"/{ad_id}" in src or f"items/{id_prefix}/{ad_id}" in src

        # Ищем изображения в галерее
        for img in soup.select('.j-view-images img, .j-view-images-frame img'):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy")
            if src and '/items/' in src and is_own_photo(src):
                # Предпочитаем полноразмерные (v) вместо thumbnails (s/m)
                full_url = urljoin(BASE_URL, src)
                # Конвертируем thumbnail в полноразмерное если нужно
                if f"{ad_id}s" in full_url:
                    full_url = full_url.replace(f"{ad_id}s", f"{ad_id}v")
                elif f"{ad_id}m" in full_url:
                    full_url = full_url.replace(f"{ad_id}m", f"{ad_id}v")
                if full_url not in photos:
                    photos.append(full_url)

        # Альтернативный поиск
        for img in soup.select('img[src*="/items/"]'):
            src = img.get("src")
            if src and is_own_photo(src):
                full_url = urljoin(BASE_URL, src)
                if f"{ad_id}s" in full_url:
                    full_url = full_url.replace(f"{ad_id}s", f"{ad_id}v")
                elif f"{ad_id}m" in full_url:
                    full_url = full_url.replace(f"{ad_id}m", f"{ad_id}v")
                if full_url not in photos:
                    photos.append(full_url)

        return photos

    def _extract_phone(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечь телефон"""
        # Ищем ссылки tel:
        tel_link = soup.select_one('a[href^="tel:"]')
        if tel_link:
            href = tel_link.get("href", "")
            phone = href.replace("tel:", "").strip()
            normalized = self._normalize_phone(phone)
            if normalized:
                return normalized

        # Паттерн для телефона
        phone_pattern = r'\+?[78][\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'

        # Ищем в тексте страницы
        text = soup.get_text()
        matches = re.findall(phone_pattern, text)
        if matches:
            return self._normalize_phone(matches[0])

        return None

    def _normalize_phone(self, phone: str) -> str:
        """Нормализовать номер телефона"""
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 11 and digits.startswith('8'):
            digits = '7' + digits[1:]
        elif len(digits) == 10:
            digits = '7' + digits
        if len(digits) == 11 and digits.startswith('7'):
            return f"+{digits}"
        return ""

    def _extract_seller_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечь имя продавца"""
        # Ищем в .vw-vendor-name (точный селектор)
        vendor_name = soup.select_one('.vw-vendor-name')
        if vendor_name:
            name = vendor_name.get_text(strip=True)
            if name and len(name) < 100:
                return name

        # Альтернативные селекторы
        for selector in ['.author-name', '.seller-name', '.user-name']:
            elem = soup.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)
                if name and 2 < len(name) < 50:
                    return name

        return None

    def _extract_telegram(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечь Telegram"""
        # Ищем в блоке контактов .j-c-telegram
        tg_elem = soup.select_one('.j-c-telegram')
        if tg_elem:
            # Может быть номер телефона или username
            href = tg_elem.get("href", "")
            text = tg_elem.get_text(strip=True)

            # Из href: t.me/username или t.me/+79...
            match = re.search(r't\.me/\+?(\d{10,})', href)
            if match:
                return match.group(1)  # Номер телефона

            match = re.search(r't\.me/([a-zA-Z]\w{4,})', href)
            if match:
                return match.group(1)  # Username

            # Из текста - убираем пробелы и дефисы если это номер
            if text:
                clean = re.sub(r'[\s\-\(\)]', '', text)
                return clean

        # Ищем другие t.me ссылки
        for tg_link in soup.select('a[href*="t.me/"]'):
            href = tg_link.get("href", "")
            # Пропускаем share ссылки
            if '/share/' in href:
                continue

            match = re.search(r't\.me/\+?(\d{10,})', href)
            if match:
                return match.group(1)

            match = re.search(r't\.me/([a-zA-Z]\w{4,})', href)
            if match:
                username = match.group(1)
                if username.lower() not in ('share', 'joinchat', 'addstickers'):
                    return username

        return None

    def _extract_city_from_url(self, url: str) -> Optional[str]:
        """Извлечь город из URL"""
        # URL: https://dnr.red/{city}/search/...
        match = re.search(r'dnr\.red/([^/]+)/search/', url)
        if match:
            city_slug = match.group(1)
            # Маппинг slug -> название
            city_names = {
                "donetsk": "Донецк",
                "makejevka": "Макеевка",
                "makeyevka": "Макеевка",
                "gorlovka": "Горловка",
                "mariupol": "Мариуполь",
                "lugansk": "Луганск",
                "harcysk": "Харцызск",
                "khartsyzsk": "Харцызск",
                "yenakievo": "Енакиево",
                "zaporozhe": "Запорожье",
                "melitopol": "Мелитополь",
                "kherson": "Херсон",
            }
            return city_names.get(city_slug, city_slug.title())
        return None

    def _extract_city(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Извлечь город"""
        # Сначала пробуем из URL
        city = self._extract_city_from_url(url)
        if city:
            return city

        # Из breadcrumbs
        breadcrumbs = soup.select("nav a, .breadcrumb a, .breadcrumbs a")
        for crumb in breadcrumbs[1:]:  # Пропускаем "Главная"
            href = crumb.get("href", "")
            text = crumb.get_text(strip=True)
            # Если это ссылка на город (не на категорию)
            if href and "/search/" not in href and text:
                if text not in ("Главная", "Объявления"):
                    return text

        return None

    def _extract_district(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечь район"""
        text = soup.get_text()

        # Известные районы
        known_districts = [
            "Калининский", "Киевский", "Кировский", "Куйбышевский",
            "Ленинский", "Петровский", "Пролетарский", "Буденновский",
            "Ворошиловский", "Центрально-Городской", "Центральный",
        ]

        for district in known_districts:
            if district.lower() in text.lower():
                return district

        # Ищем паттерны
        patterns = [
            r'(\w+(?:ский|ой))\s+район',
            r'район\s+(\w+(?:ский|ой))',
            r'р-н\s+(\w+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                district = match.group(1).strip()
                if 3 < len(district) < 30:
                    return district.title()

        return None

    def _extract_category(self, soup: BeautifulSoup, url: str) -> tuple[Optional[str], Optional[str]]:
        """Извлечь категорию и подкатегорию"""
        # Из URL
        # URL: .../search/{category}/{subcategory}/...
        match = re.search(r'/search/([^/]+)/([^/]+)/', url)
        if match:
            cat_slug, subcat_slug = match.group(1), match.group(2)

            # Маппинг категорий
            cat_names = {
                "nedvizhimost": "Недвижимость",
                "auto": "Авто",
                "elektronika": "Электроника",
                "uslugi": "Услуги",
                "rabota": "Работа",
                "zhivotnye": "Животные",
                "moda-i-stil": "Мода и стиль",
                "dom-i-sad": "Дом и сад",
                "detskiy-mir": "Детский мир",
                "biznes": "Бизнес",
                "hobbi-otdyh-i-sport": "Хобби, отдых и спорт",
                "vzaimopomoshh": "Взаимопомощь",
            }

            subcat_names = {
                "prodazha-nedvizhimosti": "Продажа",
                "arenda-nedvizhimosti": "Аренда",
                "prodazha-kvartir": "Квартиры",
                "arenda-kvartir": "Аренда квартир",
                "kommercheskaja-nedvizhimost": "Коммерческая",
                "nedvizhimost-za-rubezhom": "За рубежом",
            }

            category = cat_names.get(cat_slug, cat_slug.replace("-", " ").title())
            subcategory = subcat_names.get(subcat_slug, subcat_slug.replace("-", " ").title())

            return category, subcategory

        return None, None

    def _extract_params(self, soup: BeautifulSoup) -> dict:
        """Извлечь дополнительные параметры объявления"""
        params = {}

        # Ищем структуру vw-dynprops-item-in
        for item in soup.select(".vw-dynprops-item-in"):
            attr_elem = item.select_one(".vw-dynprops-item-attr")
            val_elem = item.select_one(".vw-dynprops-item-val")

            if attr_elem and val_elem:
                attr = attr_elem.get_text(strip=True).rstrip(":")
                val = val_elem.get_text(strip=True)
                if attr and val:
                    params[attr] = val

        return params

    def _normalize_date(self, date_str: str) -> str:
        """Привести дату к формату dd.mm.yyyy"""
        from datetime import datetime

        # Словарь месяцев
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4,
            'май': 5, 'июн': 6, 'июл': 7, 'авг': 8,
            'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12,
        }

        # Формат "16 января 2025"
        match = re.match(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
        if match:
            day, month_str, year = match.groups()
            month = months.get(month_str.lower())
            if month:
                return f"{int(day):02d}.{month:02d}.{year}"

        # Формат "16.01.2025" или "16-01-2025" или "16/01/2025"
        match = re.match(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})', date_str)
        if match:
            day, month, year = match.groups()
            if len(year) == 2:
                year = "20" + year
            return f"{int(day):02d}.{int(month):02d}.{year}"

        return date_str

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечь дату создания в формате dd.mm.yyyy"""
        from datetime import date, timedelta

        text = soup.get_text()

        # Проверяем "Сегодня", "Вчера" сначала
        if re.search(r'Создано[:\s]+Сегодня', text, re.I):
            return date.today().strftime("%d.%m.%Y")

        if re.search(r'Создано[:\s]+Вчера', text, re.I):
            yesterday = date.today() - timedelta(days=1)
            return yesterday.strftime("%d.%m.%Y")

        # Паттерны для даты
        date_patterns = [
            r'Создано[:\s]+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
            r'Добавлено[:\s]+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
            r'Создано[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
            r'Добавлено[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
            r'(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return self._normalize_date(match.group(1))

        return None

    def _is_valid_coordinates(self, lat: float, lng: float) -> bool:
        """Проверить что координаты в пределах поддерживаемых регионов"""
        # Границы регионов (примерные)
        # ДНР: lat 47.0-49.0, lng 36.5-39.5
        # ЛНР: lat 48.0-49.5, lng 38.0-40.5
        # Запорожье: lat 46.5-48.5, lng 34.0-37.0
        # Херсон: lat 46.0-47.5, lng 32.5-35.5
        # Общие границы для всех регионов:
        return 46.0 <= lat <= 49.5 and 32.5 <= lng <= 40.5

    def _reverse_geocode(self, lat: str, lng: str) -> Optional[str]:
        """Получить адрес по координатам через Nominatim"""
        try:
            import time
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json&accept-language=ru"
            headers = {"User-Agent": "ads-parser/1.0"}

            import requests
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                address = data.get("display_name", "")
                # Берём короткий адрес (без страны и области)
                parts = address.split(", ")
                if len(parts) > 2:
                    # Убираем последние 2-3 элемента (область, страна, индекс)
                    return ", ".join(parts[:-3]) if len(parts) > 3 else ", ".join(parts[:-2])
                return address
            time.sleep(1)  # Rate limit для Nominatim
        except Exception:
            pass
        return None

    def _extract_coordinates(self, html: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Извлечь координаты из JavaScript и получить адрес"""
        # Ищем jListingsMediaView.init({"addr_lat":"47.111801","addr_lon":"37.517502"})
        lat_match = re.search(r'"addr_lat"\s*:\s*"([0-9.]+)"', html)
        lng_match = re.search(r'"addr_lon"\s*:\s*"([0-9.]+)"', html)

        lat = lat_match.group(1) if lat_match else None
        lng = lng_match.group(1) if lng_match else None
        address = None

        if lat and lng:
            lat_f = float(lat)
            lng_f = float(lng)

            # Проверяем что координаты не нулевые и в пределах регионов
            if lat_f == 0 or lng_f == 0 or not self._is_valid_coordinates(lat_f, lng_f):
                return None, None, None

            # Получаем адрес
            address = self._reverse_geocode(lat, lng)

        return lat, lng, address

    def parse(self, url: str) -> Optional[Ad]:
        """
        Парсить страницу объявления

        Returns:
            Ad объект или None при ошибке
        """
        html = self.client.get(url)

        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")

        ad_id = self._extract_id(url)
        title = self._extract_title(soup)

        if not ad_id or not title:
            return None

        description = self._extract_description(soup)
        price, currency = self._extract_price(soup)
        photos = self._extract_photos(soup, ad_id)
        phone = self._extract_phone(soup)
        seller_name = self._extract_seller_name(soup)
        telegram = self._extract_telegram(soup)
        city = self._extract_city(soup, url)
        district = self._extract_district(soup)
        category, subcategory = self._extract_category(soup, url)
        date = self._extract_date(soup)
        lat, lng, address = self._extract_coordinates(html)
        params = self._extract_params(soup)

        return Ad(
            id=ad_id,
            title=title,
            description=description,
            price=price,
            currency=currency,
            photos=photos,
            phone=phone,
            seller_name=seller_name,
            telegram=telegram,
            city=city,
            district=district,
            category=category,
            subcategory=subcategory,
            date=date,
            url=url,
            lat=lat,
            lng=lng,
            address=address,
            params=params,
        )
