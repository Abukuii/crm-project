# Savdo

Do‘konlar uchun savdo, ombor, nasiya va moliya boshqaruv tizimi (ko‘p mijozli SaaS). Qurilish mollari kabi
birliklari murakkab (qop, metr, pachka) va dollar/so‘mda ishlaydigan savdoga moslangan.
To'liq texnik topshiriq: [TZ.md](TZ.md).

| Papka | Tarkibi |
|---|---|
| `backend/` | Django 5.2 + DRF API, Celery |
| `frontend/` | React + TypeScript + Vite SPA (Tailwind) |
| `infra/` | Docker Compose (prod va dev), deploy |
| `savdo_sayt/` | **Eski tizim (1.0)** — faqat ma'lumot ko'chirish uchun saqlanadi |

## Holat

Eski tizimning (1.0) barcha funksiyalari ko‘chirildi va kengaytirildi:

| Modul | Imkoniyatlar |
|---|---|
| Kassa | Qidiruv/shtrix-kod, birlik tanlash, kelishilgan narx (chegirma limiti), naqd + karta + o‘tkazma + nasiya, qaytim, chek chop etish, takroriy yuborishdan himoya |
| Savdo tarixi | Filtrlar, yig‘indi (to‘lov turlari, foyda), bekor qilish (tovar omborga qaytadi), Excel eksport |
| Mijozlar va qarzlar | Narx turi, kredit limiti, nasiya muddati, qisman/to‘liq to‘lov (FIFO), muddati o‘tgan qarzlar |
| Mahsulotlar | Birliklar (1 pachka = 10 dona), shtrix-kodlar, narx turlari va tarixi, kirill/lotin qidiruv, Excel import (tekshiruv bilan) va eksport |
| Ombor | Qoldiq jurnali, o‘rtacha tannarx, kam qolganlar, kirim hujjatlari (qo‘shimcha xarajat taqsimoti, bekor qilish) |
| Yetkazib beruvchilar | Qarz, to‘lovlar, akt sverka |
| Xarajatlar, eslatmalar | Kategoriyalar, davr bo‘yicha jami; muhimlik va muddat |
| Dashboard | Bugun/oy savdosi, sof foyda (tannarx va xarajatlar ayrilgan), haftalik grafik, TOP mahsulotlar, qarzlar, dollar kursi |
| Boshqaruv | Rollar va ruxsatlar, filiallar, PIN, audit jurnali, Telegram xabarlari, sozlamalar |
| Bosh sahifa | Animatsiyali landing va kirish formasi (`/welcome`) |

Keyingi bosqichlar (TZ 15-bo‘lim): offline kassa, smena (X/Z hisobot), qisman qaytarish, fiskal chek, Click/Payme, yetkazib berish, eski bazadan ma‘lumot ko‘chirish.

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
