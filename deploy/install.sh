#!/bin/bash
# =============================================================================
# Установка и развёртывание ads-parser на голом Ubuntu/Debian сервере
#
# Использование:
#   curl -sSL https://raw.githubusercontent.com/fitymico/ads-parser/main/deploy/install.sh | sudo bash
#
# С параметрами:
#   curl -sSL ... | sudo WORKERS=8 DELAY=0.05 bash
#
# =============================================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# =============================================================================
# Конфигурация
# =============================================================================
INSTALL_DIR="${INSTALL_DIR:-/opt/ads-parser}"
DATA_DIR="${DATA_DIR:-/data}"
REPO_URL="${REPO_URL:-https://github.com/fitymico/ads-parser.git}"
RAW_URL="${RAW_URL:-https://raw.githubusercontent.com/fitymico/ads-parser/main}"
WORKERS="${WORKERS:-6}"
DELAY="${DELAY:-0.1}"
PARSER_USER="${PARSER_USER:-parser}"

# =============================================================================
# Функции
# =============================================================================
download_files() {
    log "Загрузка файлов с GitHub..."

    local files=(
        "src/pipeline.py"
        "src/watermark.py"
        "src/config.py"
        "src/models.py"
        "src/restore_sql.py"
        "src/parser/__init__.py"
        "src/parser/client.py"
        "src/parser/listing.py"
        "src/parser/detail.py"
        "src/parser/categories.py"
        "src/mapper/__init__.py"
        "src/mapper/cities.py"
        "src/mapper/sql.py"
        "deploy/healthcheck.sh"
        "deploy/monitor.sh"
        "WaterMark.png"
    )

    for file in "${files[@]}"; do
        local dir=$(dirname "$file")
        mkdir -p "$INSTALL_DIR/$dir"
        curl -sSL "$RAW_URL/$file" -o "$INSTALL_DIR/$file" 2>/dev/null || warn "Не удалось загрузить $file"
    done

    chmod +x "$INSTALL_DIR/deploy/"*.sh 2>/dev/null || true
    chown -R "$PARSER_USER:$PARSER_USER" "$INSTALL_DIR"
}

# =============================================================================
# Баннер
# =============================================================================
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    ADS-PARSER INSTALLER                      ║"
echo "║               github.com/fitymico/ads-parser                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# =============================================================================
# Проверки
# =============================================================================
log "Проверка системы..."

if [[ $EUID -ne 0 ]]; then
   error "Скрипт должен быть запущен от root (используйте sudo)"
fi

if ! command -v apt-get &> /dev/null; then
    error "Требуется apt-get (Ubuntu/Debian)"
fi

log "  OS: $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d'"' -f2 || echo 'Unknown')"
log "  User: $PARSER_USER"
log "  Install: $INSTALL_DIR"
log "  Data: $DATA_DIR"
log "  Workers: $WORKERS, Delay: ${DELAY}s"

# =============================================================================
# Установка зависимостей
# =============================================================================
log "Установка системных пакетов..."

apt-get update -qq
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    > /dev/null 2>&1

log "Системные пакеты установлены"

# =============================================================================
# Создание пользователя
# =============================================================================
if ! id "$PARSER_USER" &>/dev/null; then
    log "Создание пользователя $PARSER_USER..."
    useradd -r -m -s /bin/bash "$PARSER_USER"
fi

# =============================================================================
# Создание директорий
# =============================================================================
log "Создание директорий..."

mkdir -p "$INSTALL_DIR"/{src/parser,src/mapper,deploy}
mkdir -p "$DATA_DIR"/{images/preview,images/images,logs,backup}

chown -R "$PARSER_USER:$PARSER_USER" "$INSTALL_DIR"
chown -R "$PARSER_USER:$PARSER_USER" "$DATA_DIR"

# =============================================================================
# Загрузка кода
# =============================================================================
cd "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
    log "Обновление репозитория..."
    sudo -u "$PARSER_USER" git pull --quiet 2>/dev/null || download_files
else
    log "Клонирование репозитория..."
    rm -rf "$INSTALL_DIR"/* 2>/dev/null || true
    sudo -u "$PARSER_USER" git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || download_files
fi

# =============================================================================
# Python окружение
# =============================================================================
log "Настройка Python..."

if [ ! -d "$INSTALL_DIR/venv" ]; then
    sudo -u "$PARSER_USER" python3 -m venv "$INSTALL_DIR/venv"
fi

sudo -u "$PARSER_USER" "$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$PARSER_USER" "$INSTALL_DIR/venv/bin/pip" install --quiet \
    requests beautifulsoup4 lxml Pillow numpy scipy

log "Python пакеты установлены"

# =============================================================================
# Systemd сервисы
# =============================================================================
log "Настройка systemd..."

cat > /etc/systemd/system/ads-parser.service << EOF
[Unit]
Description=Ads Parser Pipeline
After=network.target

[Service]
Type=simple
User=$PARSER_USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python3 src/pipeline.py --workers $WORKERS --delay $DELAY -d $DATA_DIR/images -o $DATA_DIR/export.sql --journal $DATA_DIR/processed_ids.txt --image-map $DATA_DIR/image_map.json
Restart=on-failure
RestartSec=30
StandardOutput=append:$DATA_DIR/logs/pipeline.log
StandardError=append:$DATA_DIR/logs/pipeline.log

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/ads-watermark.service << EOF
[Unit]
Description=Ads Parser Watermark Daemon
After=network.target

[Service]
Type=simple
User=$PARSER_USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python3 src/watermark.py --watch $DATA_DIR/images/preview/ -w $INSTALL_DIR/WaterMark.png
Restart=always
RestartSec=10
StandardOutput=append:$DATA_DIR/logs/watermark.log
StandardError=append:$DATA_DIR/logs/watermark.log

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/ads-healthcheck.service << EOF
[Unit]
Description=Ads Parser Healthcheck

[Service]
Type=oneshot
User=$PARSER_USER
Environment=DATA_DIR=$DATA_DIR
Environment=INSTALL_DIR=$INSTALL_DIR
ExecStart=$INSTALL_DIR/deploy/healthcheck.sh
EOF

cat > /etc/systemd/system/ads-healthcheck.timer << EOF
[Unit]
Description=Run Ads Parser Healthcheck every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
log "Systemd сервисы созданы"

# =============================================================================
# CLI команда
# =============================================================================
log "Создание CLI..."

cat > /usr/local/bin/ads-parser << 'EOFCTL'
#!/bin/bash
DATA_DIR="${DATA_DIR:-/data}"
INSTALL_DIR="${INSTALL_DIR:-/opt/ads-parser}"

case "$1" in
    start)
        systemctl start ads-parser ads-watermark ads-healthcheck.timer
        echo "✓ Парсер запущен"
        ;;
    stop)
        systemctl stop ads-parser ads-watermark ads-healthcheck.timer
        echo "✓ Парсер остановлен"
        ;;
    restart)
        systemctl restart ads-parser ads-watermark
        echo "✓ Парсер перезапущен"
        ;;
    status)
        echo "=== PARSER ==="
        systemctl is-active ads-parser && echo "Running" || echo "Stopped"
        echo ""
        echo "=== WATERMARK ==="
        systemctl is-active ads-watermark && echo "Running" || echo "Stopped"
        ;;
    logs)
        tail -f "$DATA_DIR/logs/pipeline.log"
        ;;
    progress)
        echo "=== ПРОГРЕСС ==="
        if [ -f "$DATA_DIR/logs/pipeline.log" ]; then
            tail -5 "$DATA_DIR/logs/pipeline.log"
        fi
        echo "---"
        [ -f "$DATA_DIR/processed_ids.txt" ] && echo "Обработано: $(wc -l < "$DATA_DIR/processed_ids.txt") объявлений"
        [ -f "$DATA_DIR/export.sql" ] && echo "SQL записей: $(grep -c 'INSERT' "$DATA_DIR/export.sql" 2>/dev/null || echo 0)"
        echo "Превью: $(find "$DATA_DIR/images/preview/" -name '*.webp' 2>/dev/null | wc -l)"
        echo "Фото: $(find "$DATA_DIR/images/images/" -name '*.webp' 2>/dev/null | wc -l)"
        ;;
    health)
        "$INSTALL_DIR/deploy/healthcheck.sh"
        ;;
    monitor)
        "$INSTALL_DIR/deploy/monitor.sh"
        ;;
    backup)
        BACKUP="$DATA_DIR/backup/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP"
        cp "$DATA_DIR/export.sql" "$BACKUP/" 2>/dev/null
        cp "$DATA_DIR/processed_ids.txt" "$BACKUP/" 2>/dev/null
        cp "$DATA_DIR/image_map.json" "$BACKUP/" 2>/dev/null
        echo "✓ Бэкап: $BACKUP"
        ;;
    *)
        echo "ads-parser - управление парсером объявлений"
        echo ""
        echo "Использование: ads-parser <команда>"
        echo ""
        echo "Команды:"
        echo "  start     Запустить парсер"
        echo "  stop      Остановить парсер"
        echo "  restart   Перезапустить"
        echo "  status    Статус сервисов"
        echo "  progress  Показать прогресс"
        echo "  logs      Смотреть логи (tail -f)"
        echo "  monitor   Live мониторинг"
        echo "  health    Проверка здоровья"
        echo "  backup    Создать бэкап"
        exit 1
        ;;
esac
EOFCTL

chmod +x /usr/local/bin/ads-parser

# =============================================================================
# Готово
# =============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Директории:"
echo "  Код:    $INSTALL_DIR"
echo "  Данные: $DATA_DIR"
echo ""
echo "Команды:"
echo "  ads-parser start     - запустить парсер"
echo "  ads-parser progress  - показать прогресс"
echo "  ads-parser logs      - смотреть логи"
echo "  ads-parser monitor   - live мониторинг"
echo ""
echo "Запуск:"
echo "  ads-parser start"
echo ""
