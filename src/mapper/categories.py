"""Маппинг категорий"""

CATEGORY_NAMES = {
    "vzaimopomoshh": "Взаимопомощь",
    "nedvizhimost": "Недвижимость",
    "auto": "Авто",
    "detskiy-mir": "Детский мир",
    "elektronika": "Электроника",
    "zhivotnye": "Животные",
    "uslugi": "Услуги",
    "moda-i-stil": "Мода и стиль",
    "dom-i-sad": "Дом и сад",
    "biznes": "Бизнес",
    "rabota": "Работа",
    "hobbi-otdyh-i-sport": "Хобби, отдых и спорт",
}


def get_category_name(slug: str) -> str:
    """Получить название категории по slug"""
    return CATEGORY_NAMES.get(slug, slug)
