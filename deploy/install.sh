#!/bin/bash
# =============================================================================
# Установка и развёртывание ads-parser на голом Ubuntu/Debian сервере
# Использование: curl -sSL https://your-host/install.sh | bash
# Или: ./install.sh
# =============================================================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# =============================================================================
# Конфигурация (можно переопределить через переменные окружения)
# =============================================================================
INSTALL_DIR="${INSTALL_DIR:-/opt/ads-parser}"
DATA_DIR="${DATA_DIR:-/data}"
REPO_URL="${REPO_URL:-https://github.com/your-repo/ads-parser.git}"
WORKERS="${WORKERS:-6}"
DELAY="${DELAY:-0.1}"
USER="${PARSER_USER:-parser}"

# =============================================================================
# Проверки
# =============================================================================
log "Проверка системы..."

if [[ $EUID -ne 0 ]]; then
   error "Скрипт должен быть запущен от root"
fi

if ! command -v apt-get &> /dev/null; then
    error "Требуется apt-get (Ubuntu/Debian)"
fi

# =============================================================================
# Установка зависимостей
# =============================================================================
log "Обновление системы и установка зависимостей..."

apt-get update -qq
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    htop \
    screen \
    jq \
    > /dev/null

log "Зависимости установлены"

# =============================================================================
# Создание пользователя
# =============================================================================
if ! id "$USER" &>/dev/null; then
    log "Создание пользователя $USER..."
    useradd -r -m -s /bin/bash "$USER"
fi

# =============================================================================
# Создание директорий
# =============================================================================
log "Создание директорий..."

mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"/{images/preview,images/images,logs,backup}

chown -R "$USER:$USER" "$INSTALL_DIR"
chown -R "$USER:$USER" "$DATA_DIR"

# =============================================================================
# Клонирование/обновление репозитория
# =============================================================================
if [ -d "$INSTALL_DIR/.git" ]; then
    log "Обновление репозитория..."
    cd "$INSTALL_DIR"
    sudo -u "$USER" git pull --quiet
else
    log "Клонирование репозитория..."
    sudo -u "$USER" git clone "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
        warn "Git репозиторий недоступен, копируем локальные файлы..."
        # Если git недоступен, предполагаем что файлы уже есть
    }
fi

cd "$INSTALL_DIR"

# =============================================================================
# Python виртуальное окружение
# =============================================================================
log "Настройка Python окружения..."

if [ ! -d "$INSTALL_DIR/venv" ]; then
    sudo -u "$USER" python3 -m venv "$INSTALL_DIR/venv"
fi

sudo -u "$USER" "$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$USER" "$INSTALL_DIR/venv/bin/pip" install --quiet \
    requests \
    beautifulsoup4 \
    lxml \
    Pillow \
    numpy \
    scipy

log "Python пакеты установлены"

# =============================================================================
# Systemd сервисы
# =============================================================================
log "Настройка systemd сервисов..."

# Основной парсер
cat > /etc/systemd/system/ads-parser.service << EOF
[Unit]
Description=Ads Parser Pipeline
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python3 src/pipeline.py \\
    --workers $WORKERS \\
    --delay $DELAY \\
    -d $DATA_DIR/images \\
    -o $DATA_DIR/export.sql \\
    --journal $DATA_DIR/processed_ids.txt \\
    --image-map $DATA_DIR/image_map.json
Restart=on-failure
RestartSec=30
StandardOutput=append:$DATA_DIR/logs/pipeline.log
StandardError=append:$DATA_DIR/logs/pipeline.log

[Install]
WantedBy=multi-user.target
EOF

# Watermark демон
cat > /etc/systemd/system/ads-watermark.service << EOF
[Unit]
Description=Ads Parser Watermark Daemon
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python3 src/watermark.py \\
    --watch $DATA_DIR/images/preview/ \\
    -w $INSTALL_DIR/WaterMark.png
Restart=always
RestartSec=10
StandardOutput=append:$DATA_DIR/logs/watermark.log
StandardError=append:$DATA_DIR/logs/watermark.log

[Install]
WantedBy=multi-user.target
EOF

# Healthcheck таймер
cat > /etc/systemd/system/ads-healthcheck.service << EOF
[Unit]
Description=Ads Parser Healthcheck

[Service]
Type=oneshot
User=$USER
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
# Скрипты управления
# =============================================================================
log "Создание скриптов управления..."

mkdir -p "$INSTALL_DIR/deploy"

# Скрипт управления
cat > /usr/local/bin/ads-parser << 'EOFCTL'
#!/bin/bash
case "$1" in
    start)
        systemctl start ads-parser ads-watermark ads-healthcheck.timer
        echo "Парсер запущен"
        ;;
    stop)
        systemctl stop ads-parser ads-watermark ads-healthcheck.timer
        echo "Парсер остановлен"
        ;;
    restart)
        systemctl restart ads-parser ads-watermark
        echo "Парсер перезапущен"
        ;;
    status)
        echo "=== Parser ==="
        systemctl status ads-parser --no-pager -l | head -20
        echo ""
        echo "=== Watermark ==="
        systemctl status ads-watermark --no-pager -l | head -10
        ;;
    logs)
        tail -f /data/logs/pipeline.log
        ;;
    progress)
        echo "=== Прогресс ==="
        tail -5 /data/logs/pipeline.log
        echo "---"
        echo "Обработано: $(wc -l < /data/processed_ids.txt) объявлений"
        echo "Новых SQL: $(grep -c 'INSERT' /data/export.sql 2>/dev/null || echo 0)"
        echo "Превью: $(find /data/images/preview/ -name '*.webp' 2>/dev/null | wc -l)"
        echo "Фото: $(find /data/images/images/ -name '*.webp' 2>/dev/null | wc -l)"
        ;;
    health)
        /opt/ads-parser/deploy/healthcheck.sh
        ;;
    backup)
        BACKUP_DIR="/data/backup/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        cp /data/export.sql "$BACKUP_DIR/"
        cp /data/processed_ids.txt "$BACKUP_DIR/"
        cp /data/image_map.json "$BACKUP_DIR/" 2>/dev/null
        echo "Бэкап создан: $BACKUP_DIR"
        ;;
    *)
        echo "Использование: ads-parser {start|stop|restart|status|logs|progress|health|backup}"
        exit 1
        ;;
esac
EOFCTL

chmod +x /usr/local/bin/ads-parser

# =============================================================================
# Финал
# =============================================================================
log "Установка завершена!"

echo ""
echo "=============================================="
echo "  Ads Parser успешно установлен!"
echo "=============================================="
echo ""
echo "Директории:"
echo "  Код: $INSTALL_DIR"
echo "  Данные: $DATA_DIR"
echo ""
echo "Управление:"
echo "  ads-parser start    - запустить"
echo "  ads-parser stop     - остановить"
echo "  ads-parser status   - статус"
echo "  ads-parser progress - прогресс"
echo "  ads-parser logs     - логи"
echo "  ads-parser health   - проверка здоровья"
echo "  ads-parser backup   - создать бэкап"
echo ""
echo "Запуск: ads-parser start"
echo ""
