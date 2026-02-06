#!/bin/bash
# =============================================================================
# Детальный отчёт о прогрессе парсера
# Использование: ./progress.sh [DATA_DIR]
# =============================================================================

DATA_DIR="${1:-/data}"

# Цвета
C='\033[0;36m'  # Cyan
G='\033[0;32m'  # Green
Y='\033[1;33m'  # Yellow
R='\033[0;31m'  # Red
B='\033[1m'     # Bold
N='\033[0m'     # Reset

echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║${B}                      ADS-PARSER PROGRESS                             ${N}${C}║${N}"
echo -e "${C}║${N}                      $(date '+%Y-%m-%d %H:%M:%S')                             ${C}║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════════════════╝${N}"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# ПРОЦЕССЫ
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${G}▶ ПРОЦЕССЫ${N}"
PARSER_PID=$(pgrep -f "pipeline.py" | head -1)
WM_PID=$(pgrep -f "watermark.py" | head -1)

if [ -n "$PARSER_PID" ]; then
    PARSER_TIME=$(ps -o etime= -p $PARSER_PID 2>/dev/null | xargs)
    PARSER_CPU=$(ps -o %cpu= -p $PARSER_PID 2>/dev/null | xargs)
    PARSER_MEM=$(ps -o %mem= -p $PARSER_PID 2>/dev/null | xargs)
    echo -e "  Pipeline:  ${G}●${N} Работает"
    echo -e "             PID: $PARSER_PID | Время: $PARSER_TIME | CPU: ${PARSER_CPU}% | MEM: ${PARSER_MEM}%"
else
    echo -e "  Pipeline:  ${R}○${N} Остановлен"
fi

if [ -n "$WM_PID" ]; then
    WM_TIME=$(ps -o etime= -p $WM_PID 2>/dev/null | xargs)
    echo -e "  Watermark: ${G}●${N} Работает (PID: $WM_PID, время: $WM_TIME)"
else
    echo -e "  Watermark: ${R}○${N} Остановлен"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# ТЕКУЩАЯ ЗАДАЧА
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${G}▶ ТЕКУЩАЯ ЗАДАЧА${N}"
LOG_FILE="$DATA_DIR/logs/pipeline.log"
[ ! -f "$LOG_FILE" ] && LOG_FILE="$DATA_DIR/pipeline_v2.log"
# Все города в порядке обработки
ALL_CITIES="donetsk makeyevka gorlovka mariupol yenakievo kramatorsk slavyansk konstantinovka druzhkovka krasnoarmeysk dimitrov torez snezhnoe shahtersk khartsyzsk yasinovataya avdeevka dokuchaevsk volnovaha lugansk alchevsk krasnyy-luch severodonetsk lisichansk stahanov kommunarsk rubezhnoye sverdlovsk krasnodon bryanka pervomaysk rovenki molodogvardeysk zaporozhe melitopol berdyansk energodar tokmak vasilievka primorsk gulyaypole pologi orehov kherson kakhovka skadovsk genichesk novaya-kahovka berislav golaya-pristan chjornobayevka"
TOTAL_CITIES=51

# Проверяем skip-cities из запущенного процесса
SKIP_LIST=$(ps aux 2>/dev/null | grep 'pipeline.py' | grep -v grep | grep -o '\-\-skip-cities [^ ]*' | head -1 | cut -d' ' -f2)
SKIPPED_COUNT=0
if [ -n "$SKIP_LIST" ]; then
    SKIPPED_COUNT=$(echo "$SKIP_LIST" | tr ',' '\n' | wc -l)
fi
CITIES_TO_PROCESS=$((TOTAL_CITIES - SKIPPED_COUNT))

if [ -f "$LOG_FILE" ]; then
    # Берём только строки с прогрессом [X/Y]
    CURRENT=$(grep '^\[URLs\]' "$LOG_FILE" 2>/dev/null | grep -E '\[[0-9]+/[0-9]+\]' | tail -1)
    if [ -n "$CURRENT" ]; then
        CITY=$(echo "$CURRENT" | sed 's/\[URLs\] //' | sed 's/SKIP //' | cut -d'/' -f1)
        PROGRESS=$(echo "$CURRENT" | grep -o '\[[0-9]*/[0-9]*\]')
        CURR_NUM=$(echo "$PROGRESS" | tr -d '[]' | cut -d'/' -f1)
        TOTAL_NUM=$(echo "$PROGRESS" | tr -d '[]' | cut -d'/' -f2)
        CAT_PATH=$(echo "$CURRENT" | sed 's/\[URLs\] //' | sed 's/SKIP //' | sed 's/ (р-н.*//')
        # Находим позицию текущего города в списке
        CITY_POS=0
        POS=0
        for c in $ALL_CITIES; do
            POS=$((POS + 1))
            # Пропускаем города из skip-list
            if [ -n "$SKIP_LIST" ] && echo "$SKIP_LIST" | tr ',' '\n' | grep -q "^${c}$"; then
                continue
            fi
            if [ "$c" = "$CITY" ]; then
                CITY_POS=$POS
                break
            fi
        done

        # Считаем оставшиеся города
        REMAINING=0
        FOUND_CURRENT=0
        for c in $ALL_CITIES; do
            if [ -n "$SKIP_LIST" ] && echo "$SKIP_LIST" | tr ',' '\n' | grep -q "^${c}$"; then
                continue
            fi
            if [ "$c" = "$CITY" ]; then
                FOUND_CURRENT=1
                continue
            fi
            if [ "$FOUND_CURRENT" = "1" ]; then
                REMAINING=$((REMAINING + 1))
            fi
        done

        # Считаем номер текущего города среди необработанных
        CITY_NUM=0
        for c in $ALL_CITIES; do
            if [ -n "$SKIP_LIST" ] && echo "$SKIP_LIST" | tr ',' '\n' | grep -q "^${c}$"; then
                continue
            fi
            CITY_NUM=$((CITY_NUM + 1))
            if [ "$c" = "$CITY" ]; then
                break
            fi
        done

        echo -e "  Город:       ${Y}${B}$CITY${N} [$CITY_NUM/$CITIES_TO_PROCESS] (осталось: $REMAINING)"
        echo -e "  Категория:   $CAT_PATH"

        # Прогресс-бар
        if [ -n "$CURR_NUM" ] && [ -n "$TOTAL_NUM" ] && [ "$TOTAL_NUM" -gt 0 ]; then
            PCT=$((CURR_NUM * 100 / TOTAL_NUM))
            BAR_LEN=40
            FILLED=$((PCT * BAR_LEN / 100))
            EMPTY=$((BAR_LEN - FILLED))
            BAR=$(printf "%${FILLED}s" | tr ' ' '#')
            BAR_EMPTY=$(printf "%${EMPTY}s" | tr ' ' '-')
            echo -e "  Прогресс:    ${B}$PROGRESS${N} [${G}${BAR}${N}${BAR_EMPTY}] ${PCT}%"
        fi
    else
        echo "  (нет активных задач)"
    fi
else
    echo "  (лог не найден)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# СТАТИСТИКА ОБЪЯВЛЕНИЙ
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${G}▶ ОБЪЯВЛЕНИЯ${N}"

PROCESSED=0
[ -f "$DATA_DIR/processed_ids.txt" ] && PROCESSED=$(wc -l < "$DATA_DIR/processed_ids.txt" | xargs)

SQL_V2=0
SQL_RESTORED=0
SQL_HOME=0

[ -f "$DATA_DIR/export_v2.sql" ] && SQL_V2=$(grep -c 'INSERT' "$DATA_DIR/export_v2.sql" 2>/dev/null || echo 0)
[ -f "$DATA_DIR/export_restored.sql" ] && SQL_RESTORED=$(grep -c 'INSERT' "$DATA_DIR/export_restored.sql" 2>/dev/null || echo 0)
[ -f ~/ads-parser/export.sql ] && SQL_HOME=$(grep -c 'INSERT' ~/ads-parser/export.sql 2>/dev/null || echo 0)

if [ $SQL_RESTORED -gt 0 ]; then
    TOTAL_SQL=$((SQL_RESTORED + SQL_V2))
else
    TOTAL_SQL=$((SQL_HOME + SQL_V2))
fi

echo -e "  ┌────────────────────────────────────┐"
echo -e "  │  Обработано ID:    $(printf '%8s' $PROCESSED)       │"
echo -e "  │  SQL записей:      $(printf '%8s' $TOTAL_SQL)       │"
echo -e "  └────────────────────────────────────┘"

if [ $SQL_RESTORED -gt 0 ]; then
    echo -e "    ├─ export_restored.sql: $SQL_RESTORED"
fi
if [ $SQL_HOME -gt 0 ] && [ $SQL_RESTORED -eq 0 ]; then
    echo -e "    ├─ export.sql (home):   $SQL_HOME"
fi
if [ $SQL_V2 -gt 0 ]; then
    echo -e "    └─ export_v2.sql:       $SQL_V2 (текущий)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# ИЗОБРАЖЕНИЯ
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${G}▶ ИЗОБРАЖЕНИЯ${N}"

PREVIEW_COUNT=$(find "$DATA_DIR/images/preview/" -name '*.webp' 2>/dev/null | wc -l | xargs)
IMAGES_COUNT=$(find "$DATA_DIR/images/images/" -name '*.webp' 2>/dev/null | wc -l | xargs)
TOTAL_IMAGES=$((PREVIEW_COUNT + IMAGES_COUNT))

echo -e "  ┌────────────────────────────────────┐"
echo -e "  │  Превью:           $(printf '%8s' $PREVIEW_COUNT)       │"
echo -e "  │  Полноразмерные:   $(printf '%8s' $IMAGES_COUNT)       │"
echo -e "  │  ──────────────────────────────────│"
echo -e "  │  ВСЕГО:            $(printf '%8s' $TOTAL_IMAGES)       │"
echo -e "  └────────────────────────────────────┘"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# ВОДЯНЫЕ ЗНАКИ
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${G}▶ ВОДЯНЫЕ ЗНАКИ${N}"

WM_COUNT=$(find "$DATA_DIR/images/preview/" -name '*.wm' 2>/dev/null | wc -l | xargs)
WM_PENDING=$((PREVIEW_COUNT - WM_COUNT))

if [ $PREVIEW_COUNT -gt 0 ]; then
    WM_PCT=$((WM_COUNT * 100 / PREVIEW_COUNT))
else
    WM_PCT=0
fi

# Прогресс-бар для водяных знаков
BAR_LEN=40
FILLED=$((WM_PCT * BAR_LEN / 100))
EMPTY=$((BAR_LEN - FILLED))
BAR=$(printf "%${FILLED}s" | tr ' ' '#')
BAR_EMPTY=$(printf "%${EMPTY}s" | tr ' ' '-')

echo -e "  Обработано: ${B}$WM_COUNT${N} / $PREVIEW_COUNT"
echo -e "  Прогресс:   [${G}${BAR}${N}${BAR_EMPTY}] ${WM_PCT}%"

if [ $WM_PENDING -le 0 ]; then
    echo -e "  Статус:     ${G}✓ Все превью обработаны${N}"
else
    echo -e "  Ожидает:    ${Y}$WM_PENDING файлов${N}"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# РАЗМЕР ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${G}▶ РАЗМЕР ДАННЫХ${N}"

PREVIEW_SIZE=$(du -sh "$DATA_DIR/images/preview/" 2>/dev/null | cut -f1)
IMAGES_SIZE=$(du -sh "$DATA_DIR/images/images/" 2>/dev/null | cut -f1)
TOTAL_IMG_SIZE=$(du -sh "$DATA_DIR/images/" 2>/dev/null | cut -f1)
DATA_SIZE=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)

echo -e "  Превью:        $PREVIEW_SIZE"
echo -e "  Полноразмер:   $IMAGES_SIZE"
echo -e "  Изображения:   ${B}$TOTAL_IMG_SIZE${N}"
echo -e "  Всего данных:  ${B}$DATA_SIZE${N}"
echo ""

# Диск
DISK_INFO=$(df -h "$DATA_DIR" 2>/dev/null | tail -1)
DISK_USED=$(echo "$DISK_INFO" | awk '{print $3}')
DISK_TOTAL=$(echo "$DISK_INFO" | awk '{print $2}')
DISK_PCT=$(echo "$DISK_INFO" | awk '{print $5}')
DISK_AVAIL=$(echo "$DISK_INFO" | awk '{print $4}')

echo -e "  ${Y}Диск:${N} $DISK_USED / $DISK_TOTAL ($DISK_PCT занято, свободно: $DISK_AVAIL)"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# СКОРОСТЬ (последние 100 записей)
# ═══════════════════════════════════════════════════════════════════════════════
if [ -f "$LOG_FILE" ] && [ -n "$PARSER_PID" ]; then
    echo -e "${G}▶ ПРОИЗВОДИТЕЛЬНОСТЬ${N}"

    # Подсчёт обработанных за последнюю минуту
    RECENT_ADS=$(grep -E '^\[W[0-9]\]' "$LOG_FILE" 2>/dev/null | tail -100 | wc -l)

    # Среднее кол-во фото на объявление
    AVG_PHOTOS=$(grep -oP '\(\d+ фото\)' "$LOG_FILE" 2>/dev/null | tail -100 | grep -oP '\d+' | awk '{sum+=$1; count++} END {if(count>0) printf "%.1f", sum/count; else print "0"}')

    echo -e "  Последние 100 объявлений обработаны"
    echo -e "  Среднее фото/объявление: ${B}$AVG_PHOTOS${N}"
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ПОСЛЕДНИЕ СОБЫТИЯ
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${G}▶ ПОСЛЕДНИЕ СОБЫТИЯ${N}"
if [ -f "$LOG_FILE" ]; then
    tail -8 "$LOG_FILE" | sed 's/^/  /'
else
    echo "  (лог не найден)"
fi
echo ""

echo -e "${C}══════════════════════════════════════════════════════════════════════${N}"
