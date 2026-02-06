#!/bin/bash
# =============================================================================
# Быстрый деплой на удалённый сервер
# Использование: ./quick-deploy.sh user@host [-p port]
# =============================================================================

set -e

if [ -z "$1" ]; then
    echo "Использование: $0 user@host [-p port]"
    echo "Пример: $0 pluttan@192.168.1.254 -p 6000"
    exit 1
fi

TARGET="$1"
shift

# Парсим дополнительные аргументы
SSH_OPTS=""
SCP_OPTS=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            SSH_OPTS="$SSH_OPTS -p $2"
            SCP_OPTS="$SCP_OPTS -P $2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Quick Deploy ==="
echo "Target: $TARGET"
echo "Project: $PROJECT_DIR"
echo ""

# Создаём директории
echo "[1/4] Создание директорий..."
ssh $SSH_OPTS "$TARGET" "mkdir -p ~/ads-parser/{src/parser,src/mapper,deploy} /data/{images/preview,images/images,logs,backup}" 2>/dev/null || true

# Копируем файлы
echo "[2/4] Копирование файлов..."
scp $SCP_OPTS -r "$PROJECT_DIR/src/"* "$TARGET:~/ads-parser/src/"
scp $SCP_OPTS "$PROJECT_DIR/WaterMark.png" "$TARGET:~/ads-parser/" 2>/dev/null || true
scp $SCP_OPTS "$PROJECT_DIR/deploy/"*.sh "$TARGET:~/ads-parser/deploy/"

# Устанавливаем зависимости
echo "[3/4] Установка Python зависимостей..."
ssh $SSH_OPTS "$TARGET" "pip3 install --break-system-packages -q requests beautifulsoup4 lxml Pillow numpy scipy 2>/dev/null || pip3 install -q requests beautifulsoup4 lxml Pillow numpy scipy"

# Делаем скрипты исполняемыми
echo "[4/4] Настройка прав..."
ssh $SSH_OPTS "$TARGET" "chmod +x ~/ads-parser/deploy/*.sh"

echo ""
echo "=== Деплой завершён ==="
echo ""
echo "Запуск парсера:"
echo "  ssh $SSH_OPTS $TARGET"
echo "  cd ~/ads-parser"
echo "  nohup python3 -u src/pipeline.py --workers 6 --delay 0.1 -d /data/images -o /data/export.sql --journal /data/processed_ids.txt --image-map /data/image_map.json > /data/logs/pipeline.log 2>&1 &"
echo ""
echo "Запуск watermark:"
echo "  nohup python3 -u src/watermark.py --watch /data/images/preview/ -w WaterMark.png > /data/logs/watermark.log 2>&1 &"
echo ""
echo "Healthcheck:"
echo "  ~/ads-parser/deploy/healthcheck.sh"
