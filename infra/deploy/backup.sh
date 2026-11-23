#!/usr/bin/env bash
# PostgreSQL zaxira nusxasi: /var/backups/savdo/savdo-<sana>-<sabab>.sql.gz
# Ishlatish: backup.sh [sabab]   (masalan: daily, pre-deploy, manual)
# BACKUP_S3_URI sozlangan bo'lsa — nusxa AWS S3'ga ham yuboriladi.
set -Eeuo pipefail
source "$(dirname "$(readlink -f "$0")")/common.sh"

reason="${1:-manual}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

db_user="$(env_get POSTGRES_USER)"
db_name="$(env_get POSTGRES_DB)"
[ -n "$db_user" ] && [ -n "$db_name" ] || die "infra/.env da POSTGRES_USER/POSTGRES_DB yo'q"

if [ -z "$(dc ps -q db 2>/dev/null)" ]; then
  log "Baza konteyneri ishlamayapti — zaxira o'tkazib yuborildi (birinchi o'rnatish?)"
  exit 0
fi

file="$BACKUP_DIR/savdo-$(date '+%Y%m%d-%H%M%S')-${reason}.sql.gz"
log "Zaxira nusxa: $file"
# Vaqtinchalik faylga yozamiz — xato bo'lsa chala fayl qolmaydi
if ! dc exec -T db pg_dump -U "$db_user" -d "$db_name" --no-owner --clean --if-exists \
    | gzip -9 > "$file.part"; then
  rm -f "$file.part"
  die "pg_dump bajarilmadi"
fi
mv "$file.part" "$file"
chmod 600 "$file"
log "Tayyor: $(du -h "$file" | cut -f1)"

s3="$(env_get BACKUP_S3_URI)"
if [ -n "$s3" ]; then
  if command -v aws >/dev/null; then
    aws s3 cp --only-show-errors "$file" "${s3%/}/$(basename "$file")" \
      && log "S3'ga yuborildi: ${s3%/}/$(basename "$file")" \
      || notify "⚠️ Zaxira S3'ga yuborilmadi"
  else
    log "aws CLI o'rnatilmagan — S3 o'tkazib yuborildi"
  fi
fi

# Eski nusxalarni tozalash
keep="$(env_get BACKUP_KEEP_DAYS)"
find "$BACKUP_DIR" -name 'savdo-*.sql.gz' -mtime +"${keep:-14}" -delete
