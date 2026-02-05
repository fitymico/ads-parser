"""Модуль маппинга"""

from .categories import CATEGORY_NAMES, get_category_name
from .cities import CITY_REGIONS, get_city_region, get_city_name

__all__ = [
    "CATEGORY_NAMES",
    "get_category_name",
    "CITY_REGIONS",
    "get_city_region",
    "get_city_name",
]
