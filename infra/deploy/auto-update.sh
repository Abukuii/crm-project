#!/usr/bin/env bash
# Avtomatik yangilanish: GitHub'dagi DEPLOY_BRANCH (standart: production) o'zgargan bo'lsa —
#   1) bazaning zaxira nusxasi, 2) yangi kodni tortish, 3) qayta qurish va ishga tushirish,
#   4) sog'liqni tekshirish; ishlamasa — avvalgi versiyaga qaytish.
# systemd taymeri har 2 daqiqada ishga tushiradi. Qo'lda: auto-update.sh [--force]
set -Eeuo pipefail
source "$(dirname "$(readlink -f "$0")")/common.sh"

# Bir vaqtda faqat bitta yangilanish
exec 9>/var/lock/savdo-deploy.lock
flock -n 9 || { log "Boshqa yangilanish ketmoqda — o'tkazib yuborildi"; exit 0; }

branch="$(env_get DEPLOY_BRANCH)"
branch="${branch:-production}"
force="${1:-}"

cd "$APP_DIR"
git fetch --quiet origin "$branch" || die "GitHub'dan olib bo'lmadi (internet yoki kirish huquqi?)"
current="$(git rev-parse HEAD)"
target="$(git rev-parse "origin/$branch")"

if [ "$current" = "$target" ] && [ "$force" != "--force" ]; then
  exit 0  # yangilik yo'q
fi

short="$(git rev-parse --short "$target")"
msg="$(git log -1 --format=%s "$target")"
log "Yangi versiya: $(git rev-parse --short "$current") -> $short ($msg)"

"$APP_DIR/infra/deploy/backup.sh" pre-deploy || die "Zaxira nusxa olinmadi — yangilanish to'xtatildi"

rollback() {
  log "Yangi versiya ishlamadi — $current ga qaytilmoqda"
  git reset --hard --quiet "$current"
  IMAGE_TAG="$(git rev-parse --short "$current")" dc up -d --build --remove-orphans || true
  notify "❌ $short ishlamadi, avvalgi versiyaga qaytildi. Loglar: journalctl -u savdo-update"
  # Diqqat: yangi migratsiyalar bazaga qo'llangan bo'lishi mumkin — kerak bo'lsa
  # oxirgi pre-deploy zaxirasidan tiklang (infra/deploy/restore.sh).
  exit 1
}

git reset --hard --quiet "$target"
export IMAGE_TAG="$short"
if ! dc build --pull; then
  rollback
fi
if ! dc up -d --remove-orphans; then
  rollback
fi
if ! wait_healthy 240; then
  dc logs --tail=80 api migrate || true
  rollback
fi

docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true
log "Yangilandi: $short"
notify "✅ Yangilandi: $short — $msg"
