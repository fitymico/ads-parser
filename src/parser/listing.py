"""Парсер списка объявлений"""

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import BASE_URL, MAX_PAGES
from parser.client import HttpClient


class ListingParser:
    """Парсер страниц со списком объявлений"""

    def __init__(self, client: HttpClient):
        self.client = client

    def _build_url(
        self,
        city: Optional[str],
        mode: str = "list",
        page: int = 1,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        district_id: Optional[int] = None
    ) -> str:
        """
        Построить URL для списка объявлений

        Args:
            city: slug города
            mode: "gallery" для топ, "list" для обычных
            page: номер страницы
            category: категория (например 'nedvizhimost')
            subcategory: подкатегория (например 'arenda-nedvizhimosti')
            district_id: ID района
        """
        if city:
            base = f"{BASE_URL}/{city}/search/"
        else:
            base = f"{BASE_URL}/search/"

        # Добавляем категорию и подкатегорию в путь
        if category:
            base += f"{category}/"
            if subcategory:
                base += f"{subcategory}/"

        # gallery = топ объявления, list = обычные
        if mode == "gallery":
            params = "?lt=gallery&cur=2&fa=1"
        else:
            params = "?lt=list&cur=2"

        # Добавляем район
        if district_id:
            params += f"&rd[]={district_id}"

        if page > 1:
            return f"{base}{params}&page={page}"
        return f"{base}{params}"

    def get_total_pages(
        self,
        city: Optional[str],
        mode: str = "list",
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        district_id: Optional[int] = None
    ) -> int:
        """
        Определить количество страниц

        Args:
            city: slug города
            mode: "gallery" для топ, "list" для обычных
            category: категория
            subcategory: подкатегория
            district_id: ID района
        """
        url = self._build_url(city, mode, 1, category, subcategory, district_id)
        html = self.client.get(url)

        if not html:
            return 0

        soup = BeautifulSoup(html, "lxml")

        # Ищем пагинацию - ссылки с page=N
        max_page = 1
        for link in soup.select("a[href*='page=']"):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            match = re.search(r'page=(\d+)', href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)

            if text.isdigit():
                max_page = max(max_page, int(text))

        if max_page == 1:
            # Проверяем есть ли объявления на странице
            for link in soup.select("a[href$='.html']"):
                href = link.get("href", "")
                if re.search(r'-\d{5,}\.html$', href):
                    return 1
            return 0

        return min(max_page, MAX_PAGES)

    def get_listing_urls(
        self,
        city: Optional[str],
        mode: str = "list",
        page: int = 1,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        district_id: Optional[int] = None
    ) -> list[tuple[str, bool]]:
        """
        Получить URL объявлений со страницы списка

        Args:
            city: slug города
            mode: "gallery" для топ, "list" для обычных
            page: номер страницы
            category: категория
            subcategory: подкатегория
            district_id: ID района

        Returns:
            Список кортежей (URL, is_top)
        """
        url = self._build_url(city, mode, page, category, subcategory, district_id)
        html = self.client.get(url)

        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        results = []
        seen_urls = set()

        if mode == "gallery":
            # Gallery - все объявления топовые
            for item in soup.select(".j-item"):
                link = item.select_one("a[href$='.html']")
                if not link:
                    continue
                href = link.get("href", "")
                if href and re.search(r'-(\d{5,})\.html$', href):
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        results.append((full_url, True))  # Все топ
        else:
            # List - только секция "Обычные объявления"
            # Находим заголовок "Обычные объявления"
            regular_header = None
            for title in soup.select(".in-box-title"):
                if "Обычные объявления" in title.get_text():
                    # parent - это div.in-box-head
                    regular_header = title.parent
                    break

            if regular_header:
                # Ищем контейнер с объявлениями после заголовка
                container = regular_header.find_next_sibling()
                if container:
                    for item in container.select(".j-item"):
                        link = item.select_one("a[href$='.html']")
                        if not link:
                            continue
                        href = link.get("href", "")
                        if href and re.search(r'-(\d{5,})\.html$', href):
                            full_url = urljoin(BASE_URL, href)
                            if full_url not in seen_urls:
                                seen_urls.add(full_url)
                                results.append((full_url, False))  # Обычные

        return results

    def get_all_urls(
        self,
        city: Optional[str],
        max_pages: Optional[int] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        district_id: Optional[int] = None
    ) -> list[tuple[str, bool]]:
        """
        Получить все URL объявлений города

        Args:
            city: Город (slug) или None для всех
            max_pages: Максимум страниц для парсинга
            category: категория
            subcategory: подкатегория
            district_id: ID района

        Returns:
            Список кортежей (URL, is_top)
        """
        total_pages = self.get_total_pages(city, "list", category, subcategory, district_id)

        if max_pages:
            total_pages = min(total_pages, max_pages)

        all_urls = []

        for page in range(1, total_pages + 1):
            urls = self.get_listing_urls(city, "list", page, category, subcategory, district_id)
            all_urls.extend(urls)

            if not urls:
                break  # Пустая страница - выходим

        return all_urls
