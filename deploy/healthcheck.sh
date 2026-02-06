#!/bin/bash
# =============================================================================
# Healthcheck скрипт для ads-parser
# Проверяет работоспособность парсера и отправляет алерты
# =============================================================================

set -e

# Конфигурация
DATA_DIR="${DATA_DIR:-/data}"
INSTALL_DIR="${INSTALL_DIR:-/opt/ads-parser}"
LOG_FILE="$DATA_DIR/logs/pipeline.log"
HEALTH_LOG="$DATA_DIR/logs/healthcheck.log"
JOURNAL_FILE="$DATA_DIR/processed_ids.txt"
STATE_FILE="$DATA_DIR/logs/.healthcheck_state"

# Telegram алерты (опционально)
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# Пороги
MAX_LOG_AGE_MINUTES=10        # Лог не обновлялся дольше X минут
MAX_NO_PROGRESS_MINUTES=30    # Нет новых объявлений дольше X минут
MIN_DISK_SPACE_GB=5           # Минимум свободного места

# =============================================================================
# Функции
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$HEALTH_LOG"
}

send_alert() {
    local message="$1"
    log "ALERT: $message"

    # Telegram
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_CHAT_ID" \
            -d "text=🚨 Ads Parser Alert: $message" \
            -d "parse_mode=HTML" > /dev/null 2>&1 || true
    fi
}

send_status() {
    local message="$1"

    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_CHAT_ID" \
            -d "text=$message" \
            -d "parse_mode=HTML" > /dev/null 2>&1 || true
    fi
}

get_state() {
    local key="$1"
    if [ -f "$STATE_FILE" ]; then
        grep "^$key=" "$STATE_FILE" 2>/dev/null | cut -d= -f2 || echo ""
    fi
}

set_state() {
    local key="$1"
    local value="$2"
    mkdir -p "$(dirname "$STATE_FILE")"
    if [ -f "$STATE_FILE" ]; then
        grep -v "^$key=" "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null || true
        mv "$STATE_FILE.tmp" "$STATE_FILE"
    fi
    echo "$key=$value" >> "$STATE_FILE"
}

# =============================================================================
# Проверки
# =============================================================================

ERRORS=0
WARNINGS=0

# --- Проверка процессов ---
check_processes() {
    log "Проверка процессов..."

    # Parser
    if ! pgrep -f "pipeline.py" > /dev/null; then
        send_alert "Процесс pipeline.py не запущен!"
        ((ERRORS++))
        return 1
    fi

    # Watermark
    if ! pgrep -f "watermark.py" > /dev/null; then
        send_alert "Процесс watermark.py не запущен!"
        ((ERRORS++))
        return 1
    fi

    log "  ✓ Процессы работают"
    return 0
}

# --- Проверка активности лога ---
check_log_activity() {
    log "Проверка активности лога..."

    if [ ! -f "$LOG_FILE" ]; then
        send_alert "Лог файл не найден: $LOG_FILE"
        ((ERRORS++))
        return 1
    fi

    local log_age=$(( ($(date +%s) - $(stat -c %Y "$LOG_FILE" 2>/dev/null || stat -f %m "$LOG_FILE")) / 60 ))

    if [ "$log_age" -gt "$MAX_LOG_AGE_MINUTES" ]; then
        send_alert "Лог не обновлялся $log_age минут (порог: $MAX_LOG_AGE_MINUTES)"
        ((WARNINGS++))
        return 1
    fi

    log "  ✓ Лог активен (обновлён $log_age мин назад)"
    return 0
}

# --- Проверка прогресса ---
check_progress() {
    log "Проверка прогресса..."

    if [ ! -f "$JOURNAL_FILE" ]; then
        log "  - Журнал ещё не создан"
        return 0
    fi

    local current_count=$(wc -l < "$JOURNAL_FILE")
    local last_count=$(get_state "journal_count")
    local last_check=$(get_state "last_progress_check")
    local now=$(date +%s)

    set_state "journal_count" "$current_count"
    set_state "last_progress_check" "$now"

    if [ -n "$last_count" ] && [ -n "$last_check" ]; then
        local diff=$((current_count - last_count))
        local minutes=$(( (now - last_check) / 60 ))

        if [ "$diff" -eq 0 ] && [ "$minutes" -gt "$MAX_NO_PROGRESS_MINUTES" ]; then
            send_alert "Нет новых объявлений уже $minutes минут!"
            ((WARNINGS++))
            return 1
        fi

        log "  ✓ Прогресс: +$diff объявлений за $minutes мин (всего: $current_count)"
    else
        log "  ✓ Всего: $current_count объявлений"
    fi

    return 0
}

# --- Проверка диска ---
check_disk_space() {
    log "Проверка диска..."

    local available_gb=$(df -BG "$DATA_DIR" | awk 'NR==2 {print $4}' | tr -d 'G')

    if [ "$available_gb" -lt "$MIN_DISK_SPACE_GB" ]; then
        send_alert "Мало места на диске: ${available_gb}GB (порог: ${MIN_DISK_SPACE_GB}GB)"
        ((ERRORS++))
        return 1
    fi

    log "  ✓ Свободно: ${available_gb}GB"
    return 0
}

# --- Проверка ошибок в логе ---
check_errors() {
    log "Проверка ошибок..."

    if [ -f "$LOG_FILE" ]; then
        local recent_errors=$(tail -100 "$LOG_FILE" | grep -ci "error\|exception\|traceback" || true)

        if [ "$recent_errors" -gt 10 ]; then
            send_alert "Много ошибок в логе: $recent_errors за последние 100 строк"
            ((WARNINGS++))
            return 1
        fi

        log "  ✓ Ошибок: $recent_errors"
    fi

    return 0
}

# --- Проверка сети ---
check_network() {
    log "Проверка сети..."

    if ! curl -s --max-time 10 "https://dnr.red" > /dev/null 2>&1; then
        send_alert "Сайт dnr.red недоступен!"
        ((ERRORS++))
        return 1
    fi

    log "  ✓ dnr.red доступен"
    return 0
}

# --- Статистика ---
print_stats() {
    echo ""
    echo "=============================================="
    echo "  СТАТИСТИКА"
    echo "=============================================="

    if [ -f "$JOURNAL_FILE" ]; then
        echo "Объявлений: $(wc -l < "$JOURNAL_FILE")"
    fi

    if [ -f "$DATA_DIR/export.sql" ]; then
        echo "SQL записей: $(grep -c 'INSERT' "$DATA_DIR/export.sql" 2>/dev/null || echo 0)"
    fi

    local previews=$(find "$DATA_DIR/images/preview/" -name "*.webp" 2>/dev/null | wc -l)
    local images=$(find "$DATA_DIR/images/images/" -name "*.webp" 2>/dev/null | wc -l)
    local watermarked=$(find "$DATA_DIR/images/preview/" -name "*.wm" 2>/dev/null | wc -l)

    echo "Превью: $previews (с WM: $watermarked)"
    echo "Фото: $images"
    echo "Диск: $(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)"

    if [ -f "$LOG_FILE" ]; then
        echo ""
        echo "Последние записи лога:"
        tail -3 "$LOG_FILE"
    fi
}

# =============================================================================
# Главная логика
# =============================================================================

main() {
    log "========== Healthcheck started =========="

    check_processes
    check_log_activity
    check_progress
    check_disk_space
    check_errors
    check_network

    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        log "РЕЗУЛЬТАТ: КРИТИЧНО ($ERRORS ошибок, $WARNINGS предупреждений)"
        print_stats
        exit 2
    elif [ "$WARNINGS" -gt 0 ]; then
        log "РЕЗУЛЬТАТ: ПРЕДУПРЕЖДЕНИЕ ($WARNINGS предупреждений)"
        print_stats
        exit 1
    else
        log "РЕЗУЛЬТАТ: OK"
        print_stats
        exit 0
    fi
}

# Запуск
main "$@"
