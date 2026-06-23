import os
from dotenv import load_dotenv

load_dotenv()

# Admin Chat ID lar
_raw = os.getenv("ADMIN_CHAT_IDS", "")
ADMIN_CHAT_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()]

# Kanal ID — savdo xabarlari yuboriladi
# Kanal username: @mening_kanalim yoki raqamli ID: -1001234567890
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# CRM ma'lumotlar bazasi joyi
DB_PATH = os.getenv("DB_PATH", "../crm_project/db.sqlite3")
