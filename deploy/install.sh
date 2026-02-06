#!/bin/bash
# =============================================================================
# Установка и развёртывание ads-parser на голом Ubuntu/Debian сервере
#
# Использование:
#   sudo bash deploy/install.sh
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
REPO_URL="${REPO_URL:-}"
RAW_URL="${RAW_URL:-}"
WORKERS="${WORKERS:-6}"
DELAY="${DELAY:-0.1}"
PARSER_USER="${PARSER_USER:-parser}"

# =============================================================================
# Функции
# =============================================================================
download_files() {
    log "Загрузка файлов..."

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
echo "║                      ads-parser                               ║"
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
        # Цвета
        C='\033[0;36m'  # Cyan
        G='\033[0;32m'  # Green
        Y='\033[1;33m'  # Yellow
        R='\033[0;31m'  # Red
        B='\033[1m'     # Bold
        N='\033[0m'     # Reset

        echo ""
        echo -e "${C}╔══════════════════════════════════════════════════════════════════════╗${N}"
        echo -e "${C}║${B}                    ADS-PARSER PROGRESS                               ${N}${C}║${N}"
        echo -e "${C}║${N}                    $(date '+%Y-%m-%d %H:%M:%S')                              ${C}║${N}"
        echo -e "${C}╚══════════════════════════════════════════════════════════════════════╝${N}"
        echo ""

        # Процессы
        echo -e "${G}▶ ПРОЦЕССЫ${N}"
        PARSER_PID=$(pgrep -f "pipeline.py" | head -1)
        WM_PID=$(pgrep -f "watermark.py" | head -1)
        if [ -n "$PARSER_PID" ]; then
            PARSER_TIME=$(ps -o etime= -p $PARSER_PID 2>/dev/null | xargs)
            echo -e "  Pipeline:  ${G}●${N} Работает (PID: $PARSER_PID, время: $PARSER_TIME)"
        else
            echo -e "  Pipeline:  ${R}○${N} Остановлен"
        fi
        if [ -n "$WM_PID" ]; then
            echo -e "  Watermark: ${G}●${N} Работает (PID: $WM_PID)"
        else
            echo -e "  Watermark: ${R}○${N} Остановлен"
        fi
        echo ""

        # Текущая задача
        echo -e "${G}▶ ТЕКУЩАЯ ЗАДАЧА${N}"
        LOG_FILE="$DATA_DIR/logs/pipeline.log"
        [ ! -f "$LOG_FILE" ] && LOG_FILE="$DATA_DIR/pipeline_v2.log"
        TOTAL_CITIES=51
        if [ -f "$LOG_FILE" ]; then
            CURRENT=$(grep -E '^\[URLs\]' "$LOG_FILE" 2>/dev/null | tail -1)
            if [ -n "$CURRENT" ]; then
                CITY=$(echo "$CURRENT" | grep -oP '^\[URLs\] \K[^/]+')
                PROGRESS=$(echo "$CURRENT" | grep -oP '\[\d+/\d+\]')
                CAT=$(echo "$CURRENT" | grep -oP '^\[URLs\] [^(]+' | sed 's/\[URLs\] //')
                # Подсчёт городов
                COMPLETED_CITIES=$(grep -oP '^\[URLs\] \K[^/]+' "$LOG_FILE" 2>/dev/null | sort -u | wc -l | xargs)
                COMPLETED_CITIES=$((COMPLETED_CITIES - 1))
                [ $COMPLETED_CITIES -lt 0 ] && COMPLETED_CITIES=0
                CITY_NUM=$((COMPLETED_CITIES + 1))
                echo -e "  Город:     ${Y}${B}$CITY${N} ${C}($CITY_NUM/$TOTAL_CITIES)${N}"
                echo -e "  Категория: $CAT"
                echo -e "  Прогресс:  ${B}$PROGRESS${N}"
            fi
        fi
        echo ""

        # Статистика объявлений
        echo -e "${G}▶ ОБЪЯВЛЕНИЯ${N}"
        PROCESSED=0
        [ -f "$DATA_DIR/processed_ids.txt" ] && PROCESSED=$(wc -l < "$DATA_DIR/processed_ids.txt" | xargs)
        SQL_V1=0
        SQL_V2=0
        SQL_RESTORED=0
        SQL_HOME=0
        [ -f "$DATA_DIR/export.sql" ] && SQL_V1=$(grep -c 'INSERT' "$DATA_DIR/export.sql" 2>/dev/null || echo 0)
        [ -f "$DATA_DIR/export_v2.sql" ] && SQL_V2=$(grep -c 'INSERT' "$DATA_DIR/export_v2.sql" 2>/dev/null || echo 0)
        [ -f "$DATA_DIR/export_restored.sql" ] && SQL_RESTORED=$(grep -c 'INSERT' "$DATA_DIR/export_restored.sql" 2>/dev/null || echo 0)
        [ -f ~/ads-parser/export.sql ] && SQL_HOME=$(grep -c 'INSERT' ~/ads-parser/export.sql 2>/dev/null || echo 0)
        TOTAL_SQL=$((SQL_RESTORED + SQL_V2))
        [ $TOTAL_SQL -eq 0 ] && TOTAL_SQL=$((SQL_V1 + SQL_V2 + SQL_HOME))
        echo -e "  Обработано ID:    ${B}$PROCESSED${N}"
        echo -e "  SQL записей:      ${B}$TOTAL_SQL${N}"
        [ $SQL_RESTORED -gt 0 ] && echo -e "    └─ restored:    $SQL_RESTORED"
        [ $SQL_V2 -gt 0 ] && echo -e "    └─ v2 (текущий): $SQL_V2"
        echo ""

        # Изображения
        echo -e "${G}▶ ИЗОБРАЖЕНИЯ${N}"
        PREVIEW_COUNT=$(find "$DATA_DIR/images/preview/" -name '*.webp' 2>/dev/null | wc -l | xargs)
        IMAGES_COUNT=$(find "$DATA_DIR/images/images/" -name '*.webp' 2>/dev/null | wc -l | xargs)
        TOTAL_IMAGES=$((PREVIEW_COUNT + IMAGES_COUNT))
        echo -e "  Превью:       ${B}$PREVIEW_COUNT${N}"
        echo -e "  Полноразмер:  ${B}$IMAGES_COUNT${N}"
        echo -e "  Всего:        ${B}$TOTAL_IMAGES${N}"
        echo ""

        # Водяные знаки
        echo -e "${G}▶ ВОДЯНЫЕ ЗНАКИ${N}"
        WM_COUNT=$(find "$DATA_DIR/images/preview/" -name '*.wm' 2>/dev/null | wc -l | xargs)
        WM_PENDING=$((PREVIEW_COUNT - WM_COUNT))
        if [ $WM_PENDING -le 0 ]; then
            echo -e "  Обработано: ${G}$WM_COUNT / $PREVIEW_COUNT (100%)${N}"
            echo -e "  Статус:     ${G}✓ Всё обработано${N}"
        else
            WM_PCT=$((WM_COUNT * 100 / PREVIEW_COUNT))
            echo -e "  Обработано: ${Y}$WM_COUNT / $PREVIEW_COUNT ($WM_PCT%)${N}"
            echo -e "  Ожидает:    ${Y}$WM_PENDING${N}"
        fi
        echo ""

        # Размер данных
        echo -e "${G}▶ РАЗМЕР ДАННЫХ${N}"
        IMG_SIZE=$(du -sh "$DATA_DIR/images/" 2>/dev/null | cut -f1)
        SQL_SIZE=$(du -sh "$DATA_DIR"/*.sql ~/ads-parser/*.sql 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "?")
        TOTAL_SIZE=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
        echo -e "  Изображения: ${B}$IMG_SIZE${N}"
        echo -e "  Всего:       ${B}$TOTAL_SIZE${N}"
        DISK_INFO=$(df -h "$DATA_DIR" 2>/dev/null | tail -1 | awk '{print "  Диск: " $3 " / " $2 " (" $5 " занято)"}')
        echo -e "$DISK_INFO"
        echo ""

        # Последние записи лога
        echo -e "${G}▶ ПОСЛЕДНИЕ СОБЫТИЯ${N}"
        if [ -f "$LOG_FILE" ]; then
            tail -5 "$LOG_FILE" | sed 's/^/  /'
        else
            echo "  (лог не найден)"
        fi
        echo ""
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
    uninstall)
        echo ""
        echo -e "\033[0;31m╔══════════════════════════════════════════════════════════════╗\033[0m"
        echo -e "\033[0;31m║                  ADS-PARSER UNINSTALL                        ║\033[0m"
        echo -e "\033[0;31m╚══════════════════════════════════════════════════════════════╝\033[0m"
        echo ""
        read -p "Удалить ads-parser полностью? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Отменено"
            exit 0
        fi
        read -p "Сохранить данные ($DATA_DIR)? [Y/n] " -n 1 -r
        echo ""
        KEEP_DATA=1
        [[ $REPLY =~ ^[Nn]$ ]] && KEEP_DATA=0

        echo "[+] Остановка процессов..."
        pkill -9 -f "pipeline.py" 2>/dev/null || true
        pkill -9 -f "watermark.py" 2>/dev/null || true

        echo "[+] Удаление systemd сервисов..."
        sudo systemctl stop ads-parser ads-watermark ads-healthcheck.timer 2>/dev/null || true
        sudo systemctl disable ads-parser ads-watermark ads-healthcheck.timer 2>/dev/null || true
        sudo rm -f /etc/systemd/system/ads-parser.service
        sudo rm -f /etc/systemd/system/ads-watermark.service
        sudo rm -f /etc/systemd/system/ads-healthcheck.service
        sudo rm -f /etc/systemd/system/ads-healthcheck.timer
        sudo systemctl daemon-reload 2>/dev/null || true

        echo "[+] Удаление $INSTALL_DIR..."
        sudo rm -rf "$INSTALL_DIR"

        if [ "$KEEP_DATA" = "0" ]; then
            echo "[+] Удаление $DATA_DIR..."
            sudo rm -rf "$DATA_DIR"
        else
            echo "[!] Данные сохранены: $DATA_DIR"
        fi

        echo "[+] Удаление CLI..."
        sudo rm -f /usr/local/bin/ads-parser

        echo ""
        echo "✓ ads-parser удалён"
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
        echo "  uninstall Полное удаление"
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
echo "  ads-parser stop      - остановить парсер"
echo "  ads-parser progress  - показать прогресс"
echo "  ads-parser logs      - смотреть логи"
echo "  ads-parser monitor   - live мониторинг"
echo "  ads-parser uninstall - полное удаление"
echo ""
echo "Запуск:"
echo "  ads-parser start"
echo ""
