# План: Парсер dnr.red с экспортом в CSV

## Цель
Создать парсер для сбора объявлений с сайта dnr.red по регионам ДНР, ЛНР, Запорожье, Херсон с экспортом в CSV.

## Исследование сайта

### URL-структура
- Категории: `https://dnr.red/search/{category}/`
- Город + категория: `https://dnr.red/{city}/search/{category}/`
- Пагинация: `?page=N` (до 50 страниц на категорию)
- Объявление: `/{city}/search/.../item-{id}.html`

### Данные объявления
| Поле | Селектор/Источник |
|------|-------------------|
| ID | URL (число перед .html) |
| Заголовок | `<h1>` |
| Описание | Текстовый блок |
| Цена | Элемент с "₽" |
| Фото | `img[data-fancybox="images"]` src |
| Телефон | `a[href^="tel:"]` |
| Имя продавца | Контактный блок |
| Город | Breadcrumb |
| Район | Текст объявления |
| Категория | Breadcrumb путь |
| Дата | "Создано: ..." |
| URL | Полная ссылка |

### Категории (12)
```
vzaimopomoshh, nedvizhimost, auto, detskiy-mir, elektronika,
zhivotnye, uslugi, moda-i-stil, dom-i-sad, biznes, rabota,
hobbi-otdyh-i-sport
```

### Города по регионам
- **ДНР**: donetsk, makeyevka, gorlovka, mariupol, yenakievo, kramatorsk...
- **ЛНР**: lugansk, alchevsk, krasnyy-luch, severodonetsk, lisichansk...
- **Запорожье**: zaporozhe, melitopol, berdyansk, energodar...
- **Херсон**: kherson, kakhovka, skadovsk, genichesk...

## Архитектура

```
src/
├── config.py          # Настройки, списки категорий/городов
├── models.py          # Dataclass для объявления
├── parser/
│   ├── __init__.py
│   ├── client.py      # HTTP-клиент с retry, rate limiting
│   ├── listing.py     # Парсинг списка объявлений
│   └── detail.py      # Парсинг страницы объявления
├── mapper/
│   ├── __init__.py
│   ├── categories.py  # Маппинг категорий
│   └── cities.py      # Маппинг городов
├── export/
│   ├── __init__.py
│   └── csv_export.py  # Экспорт в CSV
├── utils/
│   ├── __init__.py
│   └── images.py      # Скачивание фото
└── main.py            # Точка входа
```

## Реализация

### 1. Базовая структура
- `config.py` - константы: USER_AGENT, RATE_LIMIT, BASE_URL, списки категорий и городов
- `models.py` - dataclass `Ad` со всеми полями объявления

### 2. HTTP-клиент (`parser/client.py`)
- requests.Session с retry
- Rate limiting (1 запрос/сек)
- Случайный User-Agent
- Обработка ошибок (404, 500, таймауты)

### 3. Парсер списка (`parser/listing.py`)
- `get_listing_urls(city, category, page)` - получить URL объявлений со страницы
- `get_total_pages(city, category)` - определить количество страниц
- BeautifulSoup для парсинга HTML

### 4. Парсер объявления (`parser/detail.py`)
- `parse_ad(url)` -> `Ad` - извлечь все данные объявления
- Извлечение: заголовок, описание, цена, фото, контакты, локация, дата

### 5. Маппинг (`mapper/`)
- `categories.py` - словарь соответствия slug -> название
- `cities.py` - словарь город -> регион

### 6. Экспорт (`export/csv_export.py`)
- `export_to_csv(ads: list[Ad], filename)` - запись в CSV
- Поля: id, title, description, price, photos, phone, seller_name, city, region, category, date, url

### 7. Скачивание фото (`utils/images.py`)
- `download_images(ad, output_dir)` - скачать фото объявления
- Сохранение в `images/{ad_id}/`

### 8. Главный скрипт (`main.py`)
```python
def main():
    1. Загрузить конфиг (города, категории)
    2. Для каждого города:
       3. Для каждой категории:
          4. Получить количество страниц
          5. Для каждой страницы:
             6. Получить URL объявлений
             7. Для каждого URL:
                8. Спарсить объявление
                9. Добавить в список
    10. Экспорт в CSV
    11. (Опционально) Скачать фото
```

## Файлы для создания

1. `src/config.py` - конфигурация
2. `src/models.py` - модель данных
3. `src/parser/__init__.py`
4. `src/parser/client.py` - HTTP клиент
5. `src/parser/listing.py` - парсер списков
6. `src/parser/detail.py` - парсер объявлений
7. `src/mapper/__init__.py`
8. `src/mapper/categories.py` - категории
9. `src/mapper/cities.py` - города
10. `src/export/__init__.py`
11. `src/export/csv_export.py` - экспорт
12. `src/utils/__init__.py`
13. `src/utils/images.py` - работа с фото
14. `src/main.py` - точка входа
15. `requirements.txt` - зависимости

## Зависимости (requirements.txt)
```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
```

## Решения по архитектуре
- **Фото**: сохраняем только URL в CSV (скачивание фото отдельным этапом позже)
- **Категории**: все 12 категорий
- **Формат**: один файл `ads.csv`

## Формат CSV
```csv
id,title,description,price,currency,photos,phone,seller_name,telegram,city,district,region,category,subcategory,date,url
1220657,"Аренда офиса...","Описание...","1000","RUB","url1;url2","+79495093636","Владислав","79495093636","Донецк","Калининский","ДНР","Недвижимость","Аренда помещений","2025-11-16","https://..."
```

## Верификация
1. Запуск парсера на 1 категории 1 города (10 объявлений)
2. Проверка CSV файла - все поля заполнены корректно
3. Полный запуск на всех регионах
