"""Модели данных для парсера"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Ad:
    """Модель объявления"""

    id: str
    title: str
    description: str
    price: Optional[str] = None
    currency: str = "RUB"
    photos: list[str] = field(default_factory=list)
    phone: Optional[str] = None
    seller_name: Optional[str] = None
    telegram: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    region: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    date: Optional[str] = None
    url: str = ""
    is_top: bool = False  # Топ/продвинутое объявление
    lat: Optional[str] = None  # Широта
    lng: Optional[str] = None  # Долгота
    address: Optional[str] = None  # Адрес (из геокодинга)
    params: dict = field(default_factory=dict)  # Доп. параметры

    def photos_str(self) -> str:
        """Фото как строка через точку с запятой"""
        return ";".join(self.photos)

    def to_dict(self) -> dict:
        """Конвертация в словарь для CSV"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": self.price or "",
            "currency": self.currency,
            "photos": self.photos_str(),
            "phone": self.phone or "",
            "seller_name": self.seller_name or "",
            "telegram": self.telegram or "",
            "city": self.city or "",
            "district": self.district or "",
            "region": self.region or "",
            "category": self.category or "",
            "subcategory": self.subcategory or "",
            "date": self.date or "",
            "url": self.url,
            "is_top": "1" if self.is_top else "0",
        }
