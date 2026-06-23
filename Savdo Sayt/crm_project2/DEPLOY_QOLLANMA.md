# 🚀 CRM Deploy Qo'llanmasi (Docker + Hetzner)

## 📁 Fayl Strukturasi
```
crm_project2/
├── Dockerfile          ← (yangi, biz yaratdik)
├── docker-compose.yml  ← (yangi, biz yaratdik)
├── .env                ← (mavjud, tahrir qiling)
├── .dockerignore       ← (yangi, biz yaratdik)
├── requirements.txt
├── manage.py
├── qurilish_crm/
└── crm/
```

---

## 1️⃣ QADAM — Fayllarni loyihaga qo'shish

Dockerfile, docker-compose.yml, .dockerignore fayllarini
`crm_project2/` papkasiga ko'chiring (manage.py bilan bir joyga).

---

## 2️⃣ QADAM — .env faylni tahrir qilish

```bash
# .env faylni oching va quyidagilarni o'zgartiring:
DEBUG=False
ALLOWED_HOSTS=mijoz1.sizningsayt.com
DJANGO_ALLOWED_HOSTS=mijoz1.sizningsayt.com
CSRF_TRUSTED_ORIGINS=https://mijoz1.sizningsayt.com
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
DB_PASSWORD=kuchli_parol_yozing
PORT=8001
```

---

## 3️⃣ QADAM — GitHub ga yuklash

```bash
# Kompyuteringizda (loyiha papkasida):
git init
git add .
git commit -m "Docker deploy uchun tayyorlandi"
git remote add origin https://github.com/sizning/crm.git
git push -u origin main
```

---

## 4️⃣ QADAM — Serverga kirish (Mobaxterm)

```bash
ssh root@SIZNING_SERVER_IP
```

---

## 5️⃣ QADAM — Docker o'rnatish (faqat 1 marta)

```bash
# Docker o'rnatish
curl -fsSL https://get.docker.com | sh

# Docker compose o'rnatish
apt install docker-compose-plugin -y

# Tekshirish
docker --version
docker compose version
```

---

## 6️⃣ QADAM — CRM ni serverga yuklash

```bash
# Serverda papka yaratish
mkdir -p /opt/crm/mijoz1
cd /opt/crm/mijoz1

# GitHub dan yuklash
git clone https://github.com/sizning/crm.git .

# .env faylni sozlash
nano .env
# (mijoz ma'lumotlarini kiriting)
```

---

## 7️⃣ QADAM — Ishga tushirish

```bash
cd /opt/crm/mijoz1

# Qurishva ishga tushirish
docker compose up -d --build

# Loglarni ko'rish
docker compose logs -f

# Admin yaratish
docker compose exec web python manage.py createsuperuser
```

---

## 8️⃣ QADAM — Nginx sozlash

```bash
# Config yaratish
nano /etc/nginx/sites-available/crm_mijoz1
# (nginx.conf.example dan nusxa oling)

# Yoqish
ln -s /etc/nginx/sites-available/crm_mijoz1 /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## 9️⃣ QADAM — SSL (bepul HTTPS)

```bash
# Certbot o'rnatish (1 marta)
apt install certbot python3-certbot-nginx -y

# SSL olish
certbot --nginx -d mijoz1.sizningsayt.com
```

---

## 🔟 YANGI MIJOZ QO'SHISH (keyingi safar)

```bash
# Yangi papka
mkdir -p /opt/crm/mijoz2
cd /opt/crm/mijoz2
git clone https://github.com/sizning/crm.git .

# .env da faqat 2 ta narsa o'zgartiring:
# PORT=8002
# ALLOWED_HOSTS=mijoz2.sizningsayt.com

# Ishga tushirish
docker compose up -d --build

# Nginx config (port 8002 bilan)
# SSL olish
certbot --nginx -d mijoz2.sizningsayt.com
```

---

## 📊 Foydali Buyruqlar

```bash
# Barcha containerlarni ko'rish
docker ps

# CRM ni to'xtatish
docker compose down

# CRM ni qayta ishga tushirish
docker compose restart

# Loglarni ko'rish
docker compose logs web

# Bazaga kirish
docker compose exec db psql -U postgres -d crm_db

# Yangi migration qilish
docker compose exec web python manage.py migrate
```

---

## ⚠️ Esda tuting

- Har bir mijoz uchun alohida PORT (8001, 8002, 8003...)
- Har bir mijoz uchun alohida domain/subdomain
- .env faylidagi parollarni hech kimga bermang
- SECRET_KEY har bir mijoz uchun har xil bo'lsin
