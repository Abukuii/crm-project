#!/usr/bin/env bash
# Zaxira nusxadan tiklash. DIQQAT: joriy bazadagi ma'lumotlar o'chiriladi!
# Ishlatish: restore.sh /var/backups/savdo/savdo-20261120-030000-daily.sql.gz
set -Eeuo pipefail
source "$(dirname "$(readlink -f "$0")")/common.sh"

file="${1:-}"
[ -f "$file" ] || die "Fayl topilmadi: '$file'. Mavjudlari: ls $BACKUP_DIR"

read -r -p "Baza '$file' holatiga qaytariladi, hozirgi ma'lumotlar o'chadi. Davom etilsinmi? (ha/yo'q) " ok
[ "$ok" = "ha" ] || { log "Bekor qilindi"; exit 0; }

"$APP_DIR/infra/deploy/backup.sh" pre-restore
log "Ilova to'xtatilmoqda"
dc stop api worker beat web
log "Tiklanmoqda: $file"
gunzip -c "$file" | dc exec -T db psql -q -v ON_ERROR_STOP=1 \
  -U "$(env_get POSTGRES_USER)" -d "$(env_get POSTGRES_DB)" >/dev/null
dc up -d
wait_healthy 240 || die "Tiklangandan keyin ilova ishga tushmadi"
log "Tiklandi"
notify "♻️ Baza zaxiradan tiklandi: $(basename "$file")"
