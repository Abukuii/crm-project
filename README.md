# Qurilish CRM 2.0

Qurilish mollari do'konlari uchun savdo, ombor, nasiya va moliya tizimi (ko'p mijozli SaaS).
To'liq texnik topshiriq: [TZ.md](TZ.md).

| Papka | Tarkibi |
|---|---|
| `backend/` | Django 5.2 + DRF API, Celery |
| `frontend/` | React + TypeScript + Vite SPA (Tailwind) |
| `infra/` | Docker Compose (prod va dev), deploy |
| `savdo_sayt/` | **Eski tizim (1.0)** — faqat ma'lumot ko'chirish uchun saqlanadi |

## Holat (bosqichlar — TZ 15-bo'lim)

- [x] **0. Tayyorgarlik**: monorepo, CI, Docker, Caddy
- [x] **1. Asos** (qisman): tenant va filiallar, foydalanuvchi/rol/ruxsatlar, JWT + PIN, audit jurnali, katalog (birliklar, shtrix-kodlar, narx turlari, narx tarixi), valyuta kursi (CBU + qo'lda)
- [x] **2. Ombor** (yadro): qoldiq jurnali, o'rtacha tannarx, qoldiq/harakat API
- [ ] Excel import, kirim/ko'chirish/inventarizatsiya hujjatlari
- [ ] 3. Kassa (POS) · 4. Mijozlar va moliya · 5. Hisobotlar va bot · 6. Ko'chirish va ishga tushirish

## Lokal ishlab chiqish

Talablar: Python 3.12, Node 22, Docker.

```powershell
# 1) PostgreSQL va Redis
docker compose -f infra/docker-compose.dev.yml up -d

# 2) Backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements/dev.txt
copy .env.example .env
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py create_tenant --name "Mening do'konim" --owner admin
.venv\Scripts\python manage.py fetch_rates
.venv\Scripts\python manage.py runserver

# 3) Frontend (yangi terminalda)
cd frontend
npm install
npm run dev   # http://localhost:5173
```

API hujjati: http://localhost:8000/api/docs/ (tizimga kirgandan keyin).

## Tekshiruvlar

```powershell
cd backend; .venv\Scripts\ruff check .; .venv\Scripts\python -m pytest
cd frontend; npm test; npm run build
```

Backend API o'zgarsa, frontend tiplarini yangilang:

```powershell
cd backend; $env:DJANGO_SETTINGS_MODULE="config.settings.test"; .venv\Scripts\python manage.py spectacular --file openapi.yml
cd frontend; npm run gen:api
```

## Arxitektura qoidalari (qisqacha)

- **Tenant izolyatsiyasi**: har bir view `TenantScopedMixin`, har bir FK `TenantRelatedField` orqali.
- **Ruxsatlar**: view'da `read_perm` / `write_perm` / `action_perms`; ko'rsatilmagan yozish amali — rad etiladi.
- **Pul**: faqat `Decimal` (`apps/core/money.py`), `float` taqiqlangan.
- **Ombor**: qoldiq faqat `inventory.services.post_moves` orqali o'zgaradi; jurnal o'zgarmas.
- **O'chirish yo'q**: mahsulot, xodim — arxivlanadi / nofaol qilinadi.
- **Audit**: muhim amallar `apps.core.audit.record` orqali yoziladi.
- **Xato formati**: `{"error": {"code", "message", "details"}}`.
