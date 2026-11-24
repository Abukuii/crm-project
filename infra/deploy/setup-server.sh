#!/usr/bin/env bash
# Savdo'ni yangi AWS EC2 (Ubuntu 22.04 / 24.04) serverga o'rnatish — BIR MARTA ishga tushiriladi.
#
#   curl -fsSL https://raw.githubusercontent.com/Abukuii/crm-project/main/infra/deploy/setup-server.sh -o setup.sh
#   sudo bash setup.sh --domain savdolarim.uz --email admin@savdolarim.uz
#
# Repozitoriy maxfiy (private) bo'lsa: --ssh  (deploy kaliti yaratiladi, GitHub'ga qo'shish so'raladi)
#
# Nima qiladi: swap, Docker, kodni /opt/savdo ga yuklash, infra/.env (tasodifiy parollar bilan),
# systemd taymerlari (har 2 daqiqada avtoyangilanish + kunlik zaxira) va birinchi ishga tushirish.
set -Eeuo pipefail

DOMAIN="savdolarim.uz"
EMAIL=""
REPO_HTTPS="https://github.com/Abukuii/crm-project.git"
REPO_SSH="git@github.com:Abukuii/crm-project.git"
BRANCH="production"
USE_SSH=0
APP_DIR="/opt/savdo"

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --repo) REPO_HTTPS="$2"; REPO_SSH="$2"; shift 2 ;;
    --ssh) USE_SSH=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Noma'lum parametr: $1"; exit 1 ;;
  esac
done
EMAIL="${EMAIL:-admin@$DOMAIN}"

log() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
[ "$(id -u)" -eq 0 ] || { echo "sudo bilan ishga tushiring"; exit 1; }
. /etc/os-release
[ "${ID:-}" = "ubuntu" ] || echo "Ogohlantirish: Ubuntu uchun yozilgan (hozir: ${PRETTY_NAME:-?})"

# ── 1. Swap (kichik instance'larda build xotira yetmay qolmasligi uchun) ──────
if [ "$(swapon --show | wc -l)" -eq 0 ] && [ "$(free -m | awk '/Mem:/ {print $2}')" -lt 3500 ]; then
  log "2 GB swap yaratilmoqda"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ── 2. Paketlar va Docker ─────────────────────────────────────────────────────
log "Tizim paketlari"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates openssl unattended-upgrades >/dev/null
if ! command -v docker >/dev/null; then
  log "Docker o'rnatilmoqda (rasmiy skript)"
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null

# ── 3. Kod ────────────────────────────────────────────────────────────────────
REPO="$REPO_HTTPS"
if [ "$USE_SSH" -eq 1 ]; then
  REPO="$REPO_SSH"
  key=/root/.ssh/savdo_deploy
  if [ ! -f "$key" ]; then
    mkdir -p /root/.ssh && chmod 700 /root/.ssh
    ssh-keygen -t ed25519 -N "" -C "savdo-deploy@$DOMAIN" -f "$key" >/dev/null
    ssh-keyscan -t ed25519 github.com >> /root/.ssh/known_hosts 2>/dev/null
  fi
  echo
  echo "GitHub → repozitoriy → Settings → Deploy keys → Add deploy key (faqat o'qish):"
  echo
  cat "$key.pub"
  echo
  read -r -p "Kalitni qo'shib bo'lgach Enter bosing..." _
  export GIT_SSH_COMMAND="ssh -i $key -o IdentitiesOnly=yes"
fi

if [ ! -d "$APP_DIR/.git" ]; then
  log "Kod yuklanmoqda: $REPO"
  git clone --quiet "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"
[ "$USE_SSH" -eq 1 ] && git config core.sshCommand "ssh -i /root/.ssh/savdo_deploy -o IdentitiesOnly=yes"
git fetch --quiet origin
if ! git rev-parse --verify --quiet "origin/$BRANCH" >/dev/null; then
  echo "Ogohlantirish: origin/$BRANCH hali yo'q (CI birinchi marta ishlamagan) — 'main' ishlatiladi"
  BRANCH="main"
fi
git checkout --quiet -B "$BRANCH" "origin/$BRANCH"
chmod +x infra/deploy/*.sh

# ── 4. Maxfiy sozlamalar ──────────────────────────────────────────────────────
ENV="$APP_DIR/infra/.env"
if [ ! -f "$ENV" ]; then
  log "infra/.env yaratilmoqda (tasodifiy parollar bilan)"
  sed \
    -e "s|^APP_DOMAIN=.*|APP_DOMAIN=$DOMAIN|" \
    -e "s|^ACME_EMAIL=.*|ACME_EMAIL=$EMAIL|" \
    -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n/+=')|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" \
    -e "s|^DEPLOY_BRANCH=.*|DEPLOY_BRANCH=$BRANCH|" \
    infra/.env.example > "$ENV"
  cores="$(nproc)"
  sed -i "s|^GUNICORN_WORKERS=.*|GUNICORN_WORKERS=$((cores * 2 + 1 > 5 ? 5 : cores * 2 + 1))|" "$ENV"
  chmod 600 "$ENV"
else
  echo "infra/.env allaqachon bor — o'zgartirilmadi"
fi

# ── 5. systemd: avtoyangilanish va zaxira ─────────────────────────────────────
log "systemd taymerlari"
cp infra/deploy/systemd/savdo-*.service infra/deploy/systemd/savdo-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now savdo-update.timer savdo-backup.timer >/dev/null

# ── 6. Birinchi ishga tushirish ───────────────────────────────────────────────
log "Birinchi ishga tushirish (build bir necha daqiqa oladi)"
APP_DIR="$APP_DIR" infra/deploy/auto-update.sh --force

# ── 7. Push bildirishnomalari uchun VAPID kalitlari ───────────────────────────
if ! grep -qE '^VAPID_PRIVATE_KEY=.+' "$ENV"; then
  log "Push bildirishnomalari uchun kalitlar yaratilmoqda"
  if keys="$(docker compose --project-directory "$APP_DIR/infra" run --rm -T api        python manage.py generate_vapid_keys --env --subject "mailto:$EMAIL" 2>/dev/null)"; then
    # Bo'sh VAPID_* qatorlarini yangilari bilan almashtiramiz
    grep -v '^VAPID_' "$ENV" > "$ENV.tmp"
    printf '%s
' "$keys" >> "$ENV.tmp"
    mv "$ENV.tmp" "$ENV"
    chmod 600 "$ENV"
    APP_DIR="$APP_DIR" "$APP_DIR/infra/deploy/auto-update.sh" --force >/dev/null
  else
    echo "Ogohlantirish: VAPID kalitlari yaratilmadi — bildirishnomalarsiz davom etamiz"
  fi
fi

cat <<EOF

✅ Savdo ishga tushdi: https://$DOMAIN
   (DNS A-yozuvi shu serverning Elastic IP manziliga qaragan bo'lishi kerak — SSL avtomatik olinadi)

Keyingi qadam — bittasini tanlang:
  • Eski savdolarim.uz ma'lumotlarini ko'chirish:
      sudo $APP_DIR/infra/deploy/import-legacy.sh old.sql --name "Do'kon nomi" --owner admin
  • Yoki bo'sh do'kon yaratish:
      cd $APP_DIR/infra && sudo docker compose exec api python manage.py create_tenant --name "Do'kon" --owner admin

Foydali buyruqlar:
  systemctl list-timers 'savdo-*'          # taymerlar
  journalctl -u savdo-update -n 100        # yangilanish loglari
  sudo $APP_DIR/infra/deploy/backup.sh     # qo'lda zaxira
EOF
