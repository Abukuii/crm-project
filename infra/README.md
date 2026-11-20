# Serverga joylash (qisqa runbook)

Server: Ubuntu 24.04, Docker o'rnatilgan, domen A-yozuvi server IP'siga yo'naltirilgan.

```bash
git clone <repo> /opt/crm && cd /opt/crm/infra
cp .env.example .env && nano .env          # barcha qiymatlarni to'ldiring
docker compose up -d --build                # migratsiya avtomatik bajariladi
docker compose exec api python manage.py create_tenant --name "Do'kon" --owner admin
docker compose exec api python manage.py fetch_rates
```

Caddy SSL sertifikatni avtomatik oladi (`APP_DOMAIN`, `ACME_EMAIL`).

Yangilash: `git pull && docker compose up -d --build`.

> Zaxira nusxa (pgBackRest/wal-g → S3), Sentry va Uptime Kuma — 6-bosqichda qo'shiladi (TZ 12-bo'lim).
