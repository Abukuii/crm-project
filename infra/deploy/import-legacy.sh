#!/usr/bin/env bash
# Eski savdolarim.uz (1.0) bazasini yangi tizimga ko'chirish.
#
# 1) Eski serverda dump oling:
#      docker compose exec -T db pg_dump -U postgres --no-owner crm_db > old.sql
# 2) Faylni yangi serverga ko'chiring (scp) va shu skriptni ishga tushiring:
#      sudo /opt/savdo/infra/deploy/import-legacy.sh old.sql --name "Do'kon nomi" --owner admin
#    Avval tekshirish uchun (hech narsa saqlanmaydi; biznes oldindan yaratilgan bo'lishi kerak):
#      sudo /opt/savdo/infra/deploy/import-legacy.sh old.sql --tenant <slug> --dry-run
#
# Eski dump vaqtinchalik alohida PostgreSQL konteyneriga yuklanadi va faqat O'QILADI.
set -Eeuo pipefail
source "$(dirname "$(readlink -f "$0")")/common.sh"

dump="${1:-}"
[ -f "$dump" ] || die "Eski dump fayli ko'rsatilmagan yoki topilmadi: '$dump'"
shift

network="savdo_default"
container="savdo-legacy-db"
password="legacy-$(openssl rand -hex 8)"

cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker network inspect "$network" >/dev/null 2>&1 || die "Avval asosiy ilovani ishga tushiring (tarmoq $network yo'q)"

"$APP_DIR/infra/deploy/backup.sh" pre-import

log "Eski baza vaqtinchalik konteynerga yuklanmoqda"
cleanup
docker run -d --name "$container" --network "$network" \
  -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=legacy postgres:16-alpine >/dev/null
for _ in $(seq 1 30); do
  docker exec "$container" pg_isready -U postgres -d legacy >/dev/null 2>&1 && break
  sleep 2
done
# Konteyner ishga tushishi bilan ichki qayta ishga tushish bo'ladi — yana kutamiz
sleep 3
docker exec "$container" pg_isready -U postgres -d legacy >/dev/null || die "Vaqtinchalik baza ishga tushmadi"
docker exec -i "$container" psql -q -U postgres -d legacy >/dev/null < "$dump" \
  || die "Dump yuklanmadi (fayl to'g'ri pg_dump formatidami?)"

log "Ko'chirish boshlandi"
dc run --rm -T api python manage.py import_legacy \
  --source "postgres://postgres:${password}@${container}:5432/legacy" "$@"
log "Tayyor. Natijani tekshiring: qoldiq va qarz summalari 'OK' bo'lishi kerak."
