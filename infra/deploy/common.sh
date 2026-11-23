# shellcheck shell=bash
# Savdo deploy skriptlari uchun umumiy funksiyalar. `source` bilan ulanadi.

APP_DIR="${APP_DIR:-/opt/savdo}"
INFRA_DIR="$APP_DIR/infra"
ENV_FILE="$INFRA_DIR/.env"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/savdo}"

log() { printf '%s [savdo] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "XATO: $*"; notify "❌ $*"; exit 1; }

# .env dagi qiymatni o'qish (faylni "source" qilmasdan — xavfsizroq)
env_get() {
  local key="$1"
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2-
}

dc() { docker compose --project-directory "$INFRA_DIR" -f "$INFRA_DIR/docker-compose.yml" "$@"; }

# Telegram'ga qisqa xabar (sozlanmagan bo'lsa — jim)
notify() {
  local token chat
  token="$(env_get TELEGRAM_BOT_TOKEN)"
  chat="$(env_get DEPLOY_TELEGRAM_CHAT_ID)"
  [ -n "$token" ] && [ -n "$chat" ] || return 0
  curl -fsS -m 10 "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${chat}" \
    --data-urlencode "text=[$(env_get APP_DOMAIN)] $*" >/dev/null || true
}

# api konteyneri "healthy" bo'lguncha kutish (sekundlarda limit)
wait_healthy() {
  local limit="${1:-180}" waited=0 cid status
  while [ "$waited" -lt "$limit" ]; do
    cid="$(dc ps -q api 2>/dev/null || true)"
    if [ -n "$cid" ]; then
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$cid" 2>/dev/null || true)"
      [ "$status" = "healthy" ] && return 0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  return 1
}
