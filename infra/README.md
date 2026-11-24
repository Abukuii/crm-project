# Savdo — AWS'ga joylash va avtomatik yangilanish

Hozirgi `savdolarim.uz` (eski 1.0 versiya) → yangi **Savdo 2.0** ga o'tish qo'llanmasi.

## Qanday ishlaydi

```
Siz: git push → main
        │
        ▼
GitHub Actions (CI): lint + testlar (PostgreSQL) + build
        │  hammasi yashil bo'lsa
        ▼
"production" branch ← shu commit
        │
        ▼  (server har 2 daqiqada tekshiradi — systemd taymer)
AWS EC2: auto-update.sh
   1. bazaning zaxira nusxasi (pre-deploy)
   2. git: production'ni tortish
   3. docker compose build + up (migratsiyalar avtomatik)
   4. /api/health/ tekshiruvi — ishlamasa avvalgi versiyaga qaytadi
   5. Telegram'ga xabar (sozlangan bo'lsa)
```

Testdan o'tmagan kod hech qachon serverga chiqmaydi. Serverda hech narsani qo'lda yangilash shart emas.

## 1. AWS'da server tayyorlash (bir marta)

1. **EC2 instance**: Ubuntu 24.04 LTS, kamida **t3.small** (2 GB RAM; build uchun 2 GB swap avtomatik qo'shiladi),
   disk 20–30 GB gp3. Region — imkon qadar yaqin (masalan, `eu-central-1` Frankfurt).
2. **Security group** (kiruvchi):
   | Port | Kimga | Nima uchun |
   |---|---|---|
   | 22 | faqat sizning IP | SSH |
   | 80, 443 (TCP) | 0.0.0.0/0 | sayt va SSL |
   | 443 (UDP) | 0.0.0.0/0 | HTTP/3 (ixtiyoriy) |
3. **Elastic IP** ajrating va instance'ga biriktiring (aks holda qayta ishga tushganda IP o'zgaradi).
4. **DNS**: domen boshqaruv panelida `savdolarim.uz` va `www.savdolarim.uz` uchun **A**-yozuvni Elastic IP'ga
   yo'naltiring. ⚠️ Buni eski saytdan ma'lumot ko'chirib bo'lgandan keyin qiling (5-qadam).
5. (Ixtiyoriy) Zaxiralarni S3'ga yuborish: S3 bucket yarating, instance'ga `s3:PutObject` huquqli IAM role
   biriktiring, serverda `sudo apt install -y awscli`, `infra/.env` da `BACKUP_S3_URI=s3://bucket/savdo`.

## 2. O'rnatish (bir buyruq)

SSH orqali serverga kiring va:

```bash
curl -fsSL https://raw.githubusercontent.com/Abukuii/crm-project/main/infra/deploy/setup-server.sh -o setup.sh
sudo bash setup.sh --domain savdolarim.uz --email admin@savdolarim.uz
```

Repozitoriy **private** bo'lsa, `--ssh` qo'shing: skript deploy kaliti yaratadi va uni GitHub →
Settings → Deploy keys ga qo'shishni so'raydi (faqat o'qish huquqi). `curl` ishlamasa, skriptni
`scp` bilan ko'chiring.

Skript: swap, Docker, kod (`/opt/savdo`), tasodifiy parollar bilan `infra/.env`, systemd taymerlari va
birinchi ishga tushirish.

## 3. GitHub sozlamasi (bir marta)

Repozitoriy → **Settings → Actions → General → Workflow permissions** → **Read and write permissions**.
(CI `production` branch'ini yangilashi uchun kerak.) Shundan keyin `main` ga har bir push o'zi deploy bo'ladi.

## 3.1. Push bildirishnomalar (PWA)

Yangi server `setup-server.sh` orqali ko'tarilsa, VAPID kalitlari o'zi yaratiladi. Allaqachon
ishlayotgan serverda esa bir marta qo'lda qo'shiladi:

```bash
cd /opt/savdo/infra
sudo docker compose run --rm api python manage.py generate_vapid_keys --env | sudo tee -a .env
sudo docker compose up -d
```

Shundan keyin xodim saytga kirib **Profil → Bildirishnomalar → Yoqish** tugmasini bosadi.
Kalitlarni keyinchalik almashtirmang: eski obunalar ishlamay qoladi va hamma qaytadan yoqishi kerak.

## 4. Eski savdolarim.uz ma'lumotlarini ko'chirish

Eski serverda (eski `crm_project2` papkasida):

```bash
docker compose exec -T db pg_dump -U postgres --no-owner crm_db > old.sql
scp old.sql ubuntu@<YANGI_SERVER_IP>:~/
```

Yangi serverda — avval tekshiruv (hech narsa saqlanmaydi), keyin haqiqiy ko'chirish:

```bash
# Bo'sh biznes yaratib, unga tekshiruv:
cd /opt/savdo/infra && sudo docker compose exec api python manage.py create_tenant --name "Savdolarim" --owner admin
sudo /opt/savdo/infra/deploy/import-legacy.sh ~/old.sql --tenant savdolarim --dry-run
# Natija yaxshi bo'lsa — haqiqiy:
sudo /opt/savdo/infra/deploy/import-legacy.sh ~/old.sql --tenant savdolarim
```

Hisobot oxirida **"Qoldiq ... OK"** va **"Ochiq qarz ... OK"** chiqishi kerak.
Eski foydalanuvchilar **eski parollari bilan** kiradi (login band bo'lsa — `savdolarim_<login>`).

Ko'chiriladi: mahsulotlar va qoldiq, mijozlar, savdo tarixi, nasiya qarzlar va to'lovlar, xarajatlar,
eslatmalar, dollar kursi, foydalanuvchilar. Eski tizimda xarid narxi saqlanmagan mahsulotlar uchun
tannarx = sotish narxi (hisobotda ko'rsatiladi) — keyingi kirimlarda haqiqiy narx kiritilsa tuzaladi.

## 5. Domenni almashtirish (o'tish kuni)

1. Eski saytda savdoni to'xtating (kassirlarni ogohlantiring).
2. Yangi `old.sql` oling va 4-qadamdagi haqiqiy ko'chirishni bajaring.
3. DNS A-yozuvini yangi serverga o'zgartiring. SSL sertifikat birinchi so'rovda avtomatik olinadi.
4. Eski serverni bir necha kun o'chirmay turing (faqat o'qish uchun).

## Kundalik foydalanish

| Vazifa | Buyruq |
|---|---|
| Yangilanish holati | `journalctl -u savdo-update -n 100` |
| Taymerlar | `systemctl list-timers 'savdo-*'` |
| Hozir yangilash | `sudo /opt/savdo/infra/deploy/auto-update.sh --force` |
| Loglar | `cd /opt/savdo/infra && sudo docker compose logs -f api` |
| Qo'lda zaxira | `sudo /opt/savdo/infra/deploy/backup.sh manual` |
| Zaxiradan tiklash | `sudo /opt/savdo/infra/deploy/restore.sh /var/backups/savdo/<fayl>.sql.gz` |
| Yangi do'kon | `cd /opt/savdo/infra && sudo docker compose exec api python manage.py create_tenant --name "..." --owner ...` |
| Django admin | `https://savdolarim.uz/admin/` (superuser: `docker compose exec api python manage.py createsuperuser`) |

Zaxiralar: `/var/backups/savdo/` — har kuni 03:00 va har yangilanishdan oldin, 14 kun saqlanadi.

## Muammolar

- **Yangilanish ishlamadi** → server avvalgi versiyaga qaytadi va Telegram'ga xabar yuboradi.
  Agar yangi migratsiya bazaga qo'llangan bo'lsa, `pre-deploy` zaxirasidan `restore.sh` bilan tiklang.
- **SSL olinmadi** → DNS A-yozuvi serverga qaraganini va 80/443 portlar ochiqligini tekshiring:
  `sudo docker compose logs web`.
- **Markaziy bank kursi kelmayapti** → cbu.uz ba'zan javob bermaydi yoki xorijiy IP'larni cheklaydi.
  Tizim qayta urinadi; shu orada Sozlamalarda "Do'kon kursi (qo'lda)" ni tanlang.
