"""
notify.py — CRM views.py dan chaqiriladi.
requests library bilan ishlaydi (asyncio muammosi yo'q).
"""
import os
import logging

logger = logging.getLogger(__name__)


def send_savdo_notify(savdo_data: dict):
    try:
        import requests
        from dotenv import load_dotenv

        bot_dir = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(bot_dir, '.env'))

        bot_token = os.getenv("BOT_TOKEN", "")
        channel_id = os.getenv("CHANNEL_ID", "")

        print(f"[NOTIFY] token={bot_token[:10]}... channel={channel_id}")

        if not bot_token or not channel_id:
            print("[NOTIFY] BOT_TOKEN yoki CHANNEL_ID yo'q!")
            return

        tolov_map = {
            'naqd': '💵 Naqd pul',
            'plastik': '💳 Plastik karta',
            'nasiya': '📋 Nasiya'
        }
        tolov_nomi = tolov_map.get(savdo_data['tolov_turi'], savdo_data['tolov_turi'])

        lines = [
            "🛒 <b>Yangi Savdo!</b>",
            f"📅 {savdo_data['sana']}",
            f"👨‍💼 Sotuvchi: <b>{savdo_data['sotuvchi']}</b>",
            "",
            "📋 <b>Mahsulotlar:</b>",
        ]
        for item in savdo_data['itemlar']:
            lines.append(f"  • {item['nomi']} × {item['soni']} = {item['jami']:,} so'm")

        lines += [
            "",
            f"💳 To'lov: <b>{tolov_nomi}</b>",
            f"💰 Jami: <b>{savdo_data['jami_summa']:,} so'm</b>",
        ]

        if savdo_data['tolov_turi'] == 'nasiya' and savdo_data.get('mijoz_ism'):
            lines += [
                "",
                "👤 <b>Haridor:</b>",
                f"   Ismi: <b>{savdo_data['mijoz_ism']}</b>",
                f"   📞 Tel: {savdo_data['mijoz_tel']}",
            ]

        text = "\n".join(lines)

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = requests.post(url, json={
            "chat_id": channel_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)

        print(f"[NOTIFY] Telegram javob: {response.status_code} — {response.text}")

    except Exception as e:
        print(f"[NOTIFY] XATO: {e}")
        logger.error(f"Telegram xabari xatosi: {e}")