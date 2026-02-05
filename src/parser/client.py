"""HTTP-клиент с retry и rate limiting"""

import random
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    USER_AGENTS,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)


class HttpClient:
    """HTTP-клиент с поддержкой retry и rate limiting"""

    def __init__(self):
        self.session = self._create_session()
        self._last_request_time: float = 0

    def _create_session(self) -> requests.Session:
        """Создать сессию с retry стратегией"""
        session = requests.Session()

        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_DELAY,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_headers(self) -> dict:
        """Получить заголовки с случайным User-Agent"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def _rate_limit(self) -> None:
        """Соблюдение rate limit"""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

    def get(self, url: str) -> Optional[str]:
        """
        Выполнить GET-запрос с rate limiting

        Returns:
            HTML контент или None при ошибке
        """
        self._rate_limit()

        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            self._last_request_time = time.time()

            if response.status_code == 404:
                return None

            response.raise_for_status()
            return response.text

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса {url}: {e}")
            self._last_request_time = time.time()
            return None

    def download(self, url: str, path: str) -> bool:
        """
        Скачать файл

        Returns:
            True при успехе
        """
        self._rate_limit()

        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=REQUEST_TIMEOUT,
                stream=True,
            )
            self._last_request_time = time.time()

            response.raise_for_status()

            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True

        except requests.exceptions.RequestException as e:
            print(f"Ошибка скачивания {url}: {e}")
            self._last_request_time = time.time()
            return False

    def close(self) -> None:
        """Закрыть сессию"""
        self.session.close()
