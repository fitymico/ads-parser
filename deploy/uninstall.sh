#!/bin/bash
# =============================================================================
# Полное удаление ads-parser
#
# Использование:
#   sudo bash deploy/uninstall.sh
#
# Или локально:
#   sudo ./uninstall.sh
#
# С сохранением данных:
#   curl -sSL ... | sudo KEEP_DATA=1 bash
# =============================================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

# Конфигурация
INSTALL_DIR="${INSTALL_DIR:-/opt/ads-parser}"
DATA_DIR="${DATA_DIR:-/data}"
PARSER_USER="${PARSER_USER:-parser}"
KEEP_DATA="${KEEP_DATA:-0}"

echo ""
echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║                  ADS-PARSER UNINSTALLER                      ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR]${NC} Скрипт должен быть запущен от root (используйте sudo)"
   exit 1
fi

# Остановка процессов
log "Остановка процессов..."
pkill -9 -f "pipeline.py" 2>/dev/null || true
pkill -9 -f "watermark.py" 2>/dev/null || true

# Остановка и удаление systemd сервисов
log "Удаление systemd сервисов..."
systemctl stop ads-parser ads-watermark ads-healthcheck.timer 2>/dev/null || true
systemctl disable ads-parser ads-watermark ads-healthcheck.timer 2>/dev/null || true
rm -f /etc/systemd/system/ads-parser.service
rm -f /etc/systemd/system/ads-watermark.service
rm -f /etc/systemd/system/ads-healthcheck.service
rm -f /etc/systemd/system/ads-healthcheck.timer
systemctl daemon-reload 2>/dev/null || true

# Удаление CLI
log "Удаление CLI..."
rm -f /usr/local/bin/ads-parser

# Удаление кода
log "Удаление $INSTALL_DIR..."
rm -rf "$INSTALL_DIR"

# Удаление данных
if [ "$KEEP_DATA" = "1" ]; then
    warn "Данные сохранены: $DATA_DIR"
else
    log "Удаление данных $DATA_DIR..."
    rm -rf "$DATA_DIR"
fi

# Удаление пользователя
if id "$PARSER_USER" &>/dev/null; then
    log "Удаление пользователя $PARSER_USER..."
    userdel -r "$PARSER_USER" 2>/dev/null || userdel "$PARSER_USER" 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                   УДАЛЕНИЕ ЗАВЕРШЕНО                         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Удалено:"
echo "  - Systemd сервисы"
echo "  - $INSTALL_DIR"
[ "$KEEP_DATA" != "1" ] && echo "  - $DATA_DIR"
echo "  - /usr/local/bin/ads-parser"
echo "  - Пользователь $PARSER_USER"
echo ""
