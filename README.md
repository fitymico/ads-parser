# ads-parser

Парсер объявлений с сайта dnr.red. Собирает объявления, изображения и генерирует SQL для импорта в базу данных.

## Возможности

- Парсинг всех объявлений по регионам: ДНР, ЛНР, Запорожье, Херсон
- Deep scan режим для обхода лимита в 50 страниц (итерация по категориям × районам)
- Автоматический выбор режима: простой скан для маленьких городов, deep scan для больших
- Параллельная обработка с настраиваемым количеством воркеров
- Скачивание и сжатие изображений (превью + полноразмерные)
- Наложение водяного знака на превью
- Инкрементальная запись SQL (не теряется при падении)
- Resume: продолжение с места остановки через журнал
- Детерминированные имена файлов (md5 от URL)

## Установка

### Одной командой (Ubuntu/Debian)

```bash
curl -sSL https://raw.githubusercontent.com/fitymico/ads-parser/main/deploy/install.sh | sudo bash
```

С параметрами:
```bash
curl -sSL https://raw.githubusercontent.com/fitymico/ads-parser/main/deploy/install.sh | sudo WORKERS=8 DELAY=0.05 bash
```

### Ручная установка

```bash
git clone https://github.com/fitymico/ads-parser.git
cd ads-parser
pip3 install requests beautifulsoup4 lxml Pillow numpy scipy
```

## Использование

### Запуск парсера

```bash
# Базовый запуск
python3 -u src/pipeline.py \
    --workers 6 \
    --delay 0.1 \
    -d /data/images \
    -o /data/export.sql \
    --journal /data/processed_ids.txt \
    --image-map /data/image_map.json

# Пропустить уже обработанные города
python3 -u src/pipeline.py \
    --skip-cities "donetsk,makeyevka,gorlovka" \
    ...

# Только один город
python3 -u src/pipeline.py -c donetsk ...

# Только регион
python3 -u src/pipeline.py -r ДНР ...
```

### Параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--workers` | Количество воркеров | 4 |
| `--delay` | Задержка между запросами (сек) | 0.15 |
| `-d, --images-dir` | Директория для изображений | ./images |
| `-o, --output` | SQL файл | ./export.sql |
| `--journal` | Журнал обработанных ID | ./processed_ids.txt |
| `--image-map` | Маппинг URL→файл | ./image_map.json |
| `--skip-cities` | Пропустить города (через запятую) | - |
| `-c, --city` | Только один город | - |
| `-r, --region` | Только регион (ДНР/ЛНР/Запорожье/Херсон) | - |
| `--deep-scan` | Глубокий скан по категориям | true |
| `--simple-scan` | Простой скан (без категорий) | false |

### Водяной знак

```bash
# Тест на одном файле
python3 src/watermark.py --test preview.webp -w WaterMark.png

# Обработать папку
python3 src/watermark.py --dir /data/images/preview/ -w WaterMark.png

# Демон (следит за папкой)
python3 -u src/watermark.py --watch /data/images/preview/ -w WaterMark.png
```

## Структура проекта

```
ads-parser/
├── src/
│   ├── pipeline.py      # Основной конвейер
│   ├── watermark.py     # Наложение водяного знака
│   ├── config.py        # Конфигурация городов
│   ├── models.py        # Модели данных
│   ├── parser/
│   │   ├── client.py    # HTTP клиент
│   │   ├── listing.py   # Парсер листингов
│   │   ├── detail.py    # Парсер страниц объявлений
│   │   └── categories.py # Категории и районы
│   └── mapper/
│       ├── cities.py    # Маппинг городов
│       └── sql.py       # Генерация SQL
├── deploy/
│   ├── install.sh       # Полная установка
│   ├── quick-deploy.sh  # Быстрый деплой
│   ├── healthcheck.sh   # Проверка здоровья
│   └── monitor.sh       # Live мониторинг
└── WaterMark.png        # Водяной знак
```

## Выходные данные

### SQL

Генерируется файл с INSERT запросами для таблицы объявлений:

```sql
INSERT INTO ads (user_id, city_id, region_id, category_id, ...) VALUES (...);
```

### Изображения

```
images/
├── preview/     # Превью (с водяным знаком)
│   ├── abc123.webp
│   └── abc123.webp.wm  # Маркер обработки WM
└── images/      # Полноразмерные (обрезанные, сжатые)
    └── def456.webp
```

## Мониторинг

### Healthcheck

```bash
./deploy/healthcheck.sh
```

Проверяет:
- Процессы запущены
- Лог обновляется
- Есть прогресс
- Место на диске
- Ошибки в логе
- Доступность сайта

Поддержка Telegram алертов:
```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
./deploy/healthcheck.sh
```

### Live мониторинг

```bash
./deploy/monitor.sh
```

## Systemd (после install.sh)

```bash
# Управление
ads-parser start
ads-parser stop
ads-parser status
ads-parser progress
ads-parser logs
ads-parser health
ads-parser backup
```

## Лицензия

MIT
