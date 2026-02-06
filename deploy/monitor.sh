#!/bin/bash
# =============================================================================
# Мониторинг парсера в реальном времени
# Использование: ./monitor.sh [интервал_секунд]
# =============================================================================

DATA_DIR="${DATA_DIR:-/data}"
INTERVAL="${1:-5}"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

clear_screen() {
    printf "\033c"
}

while true; do
    clear_screen

    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           ADS-PARSER MONITOR $(date '+%H:%M:%S')                    ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Процессы
    echo -e "${GREEN}▶ ПРОЦЕССЫ${NC}"
    PARSER_PID=$(pgrep -f "pipeline.py" | head -1)
    WM_PID=$(pgrep -f "watermark.py" | head -1)

    if [ -n "$PARSER_PID" ]; then
        echo "  Pipeline: ✓ PID $PARSER_PID"
    else
        echo "  Pipeline: ✗ не запущен"
    fi

    if [ -n "$WM_PID" ]; then
        echo "  Watermark: ✓ PID $WM_PID"
    else
        echo "  Watermark: ✗ не запущен"
    fi
    echo ""

    # Статистика
    echo -e "${GREEN}▶ СТАТИСТИКА${NC}"

    if [ -f "$DATA_DIR/processed_ids.txt" ]; then
        PROCESSED=$(wc -l < "$DATA_DIR/processed_ids.txt")
        echo "  Обработано: $PROCESSED объявлений"
    fi

    if [ -f "$DATA_DIR/export.sql" ]; then
        SQL_COUNT=$(grep -c 'INSERT' "$DATA_DIR/export.sql" 2>/dev/null || echo 0)
        echo "  SQL записей: $SQL_COUNT"
    fi

    PREVIEWS=$(find "$DATA_DIR/images/preview/" -name "*.webp" 2>/dev/null | wc -l)
    WATERMARKED=$(find "$DATA_DIR/images/preview/" -name "*.wm" 2>/dev/null | wc -l)
    IMAGES=$(find "$DATA_DIR/images/images/" -name "*.webp" 2>/dev/null | wc -l)

    echo "  Превью: $PREVIEWS (WM: $WATERMARKED)"
    echo "  Фото: $IMAGES"
    echo ""

    # Диск
    echo -e "${GREEN}▶ ДИСК${NC}"
    df -h "$DATA_DIR" | tail -1 | awk '{print "  Использовано: " $3 " / " $2 " (" $5 ")"}'
    du -sh "$DATA_DIR" 2>/dev/null | awk '{print "  Данные: " $1}'
    echo ""

    # Последние логи
    echo -e "${GREEN}▶ PIPELINE LOG${NC}"
    if [ -f "$DATA_DIR/logs/pipeline.log" ]; then
        tail -5 "$DATA_DIR/logs/pipeline.log" | sed 's/^/  /'
    elif [ -f "$DATA_DIR/pipeline_v2.log" ]; then
        tail -5 "$DATA_DIR/pipeline_v2.log" | sed 's/^/  /'
    else
        echo "  (лог не найден)"
    fi
    echo ""

    echo -e "${GREEN}▶ WATERMARK LOG${NC}"
    if [ -f "$DATA_DIR/logs/watermark.log" ]; then
        tail -3 "$DATA_DIR/logs/watermark.log" | sed 's/^/  /'
    elif [ -f "$DATA_DIR/watermark.log" ]; then
        tail -3 "$DATA_DIR/watermark.log" | sed 's/^/  /'
    else
        echo "  (лог не найден)"
    fi

    echo ""
    echo -e "${YELLOW}Обновление каждые ${INTERVAL}с. Ctrl+C для выхода.${NC}"

    sleep "$INTERVAL"
done
