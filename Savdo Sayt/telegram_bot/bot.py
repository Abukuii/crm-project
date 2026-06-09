import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from database import (get_daily_report, get_monthly_stats,
                      get_qarzdorlar, get_kam_qolganlar, get_mahsulotlar_soni)
from config import ADMIN_CHAT_IDS, CHANNEL_ID

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")


# ── KLAVIATURA ────────────────────────────────────────────────
def admin_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Bugungi hisobot"), KeyboardButton(text="📈 Oylik hisobot")],
        [KeyboardButton(text="💳 Qarzdorlar"),       KeyboardButton(text="⚠️ Kam qolganlar")],
        [KeyboardButton(text="📦 Jami mahsulotlar")],
    ], resize_keyboard=True)


# ── KOMANDALAR ────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: Message):
    if is_admin(message.chat.id):
        await message.answer(
            "👷 <b>Qurilish Mollari CRM Boti</b>\n\n"
            "Salom, Admin! Quyidagi tugmalardan foydalaning:",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer(
            "👷 <b>Qurilish Mollari CRM Boti</b>\n\n"
            "Bu bot faqat adminlar uchun.\n"
            f"Sizning Chat ID: <code>{message.chat.id}</code>",
            parse_mode="HTML"
        )


@dp.message(Command("chatid"))
async def cmd_chatid(message: Message):
    await message.answer(f"🆔 Chat ID: <code>{message.chat.id}</code>", parse_mode="HTML")


# ── TUGMA HANDLERLARI ─────────────────────────────────────────
@dp.message(lambda m: m.text == "📊 Bugungi hisobot")
async def btn_bugungi(message: Message):
    if not is_admin(message.chat.id): return
    await message.answer(build_daily_report(), parse_mode="HTML")


@dp.message(lambda m: m.text == "📈 Oylik hisobot")
async def btn_oylik(message: Message):
    if not is_admin(message.chat.id): return
    await message.answer(build_monthly_report(), parse_mode="HTML")


@dp.message(lambda m: m.text == "💳 Qarzdorlar")
async def btn_qarzdorlar(message: Message):
    if not is_admin(message.chat.id): return
    await message.answer(build_qarzdorlar(), parse_mode="HTML")


@dp.message(lambda m: m.text == "⚠️ Kam qolganlar")
async def btn_kam_qolganlar(message: Message):
    if not is_admin(message.chat.id): return
    await message.answer(build_kam_qolganlar(), parse_mode="HTML")


@dp.message(lambda m: m.text == "📦 Jami mahsulotlar")
async def btn_mahsulotlar(message: Message):
    if not is_admin(message.chat.id): return
    await message.answer(build_mahsulotlar_soni(), parse_mode="HTML")


# ── HISOBOT BUILDER ───────────────────────────────────────────
def build_daily_report() -> str:
    data = get_daily_report()
    if not data:
        return "📭 Bugun hech qanday savdo amalga oshirilmagan."
    lines = [
        "📊 <b>Bugungi Savdo Hisoboti</b>",
        f"📅 {data['sana']}\n",
        f"🛒 Jami savdolar: <b>{data['savdolar_soni']} ta</b>",
        f"💵 Naqd: <b>{data['naqd']:,} so'm</b>",
        f"💳 Plastik: <b>{data['plastik']:,} so'm</b>",
        f"📋 Nasiya: <b>{data['nasiya']:,} so'm</b>",
        "━━━━━━━━━━━━━━━━━",
        f"💰 Jami daromad: <b>{data['jami']:,} so'm</b>",
    ]
    if data.get('top_mahsulotlar'):
        lines.append("\n🏆 <b>Top mahsulotlar:</b>")
        for i, m in enumerate(data['top_mahsulotlar'], 1):
            lines.append(f"  {i}. {m['nomi']} — {m['soni']} ta")
    if data.get('yangi_qarzdorlar'):
        lines.append(f"\n⚠️ Yangi nasiya: <b>{data['yangi_qarzdorlar']} ta</b>")
    return "\n".join(lines)


def build_monthly_report() -> str:
    data = get_monthly_stats()
    lines = [
        "📈 <b>Oylik Statistika</b>",
        f"📅 {data['oy']}\n",
        f"🛒 Jami savdolar: <b>{data['savdolar_soni']} ta</b>",
        f"💰 Jami daromad: <b>{data['jami_daromad']:,} so'm</b>",
        f"📋 Nasiya miqdori: <b>{data['nasiya_jami']:,} so'm</b>",
        f"👥 Yangi mijozlar: <b>{data['yangi_mijozlar']} ta</b>",
        "━━━━━━━━━━━━━━━━━",
        f"📦 Eng ko'p sotilgan: <b>{data.get('top_mahsulot', '—')}</b>",
    ]
    return "\n".join(lines)


def build_qarzdorlar() -> str:
    qarzdorlar = get_qarzdorlar()
    if not qarzdorlar:
        return "✅ <b>Qarzdor yo'q!</b> Barcha to'lovlar amalga oshirilgan."
    lines = [f"💳 <b>Qarzdorlar Ro'yxati</b>", f"Jami: {len(qarzdorlar)} ta mijoz\n"]
    jami_qarz = 0
    for q in qarzdorlar:
        lines.append(
            f"👤 <b>{q['ism']}</b>\n"
            f"   📞 {q['telefon']}\n"
            f"   💸 Qarz: {q['qarz']:,} so'm\n"
        )
        jami_qarz += q['qarz']
    lines += ["━━━━━━━━━━━━━━━━━", f"💰 Umumiy qarz: <b>{jami_qarz:,} so'm</b>"]
    return "\n".join(lines)


def build_kam_qolganlar() -> str:
    mahsulotlar = get_kam_qolganlar()
    if not mahsulotlar:
        return "✅ <b>Barcha mahsulotlar yetarli!</b>"
    lines = [f"⚠️ <b>Kam Qolgan Mahsulotlar</b>", f"Jami: {len(mahsulotlar)} ta\n"]
    for m in mahsulotlar:
        holat = "❌ Tugagan" if m['qoldi'] == 0 else f"⚠️ {m['qoldi']} ta qoldi"
        lines.append(f"📦 <b>{m['nomi']}</b> — {holat}")
    return "\n".join(lines)


def build_mahsulotlar_soni() -> str:
    data = get_mahsulotlar_soni()
    lines = [
        "📦 <b>Mahsulotlar Holati</b>\n",
        f"Jami turlar: <b>{data['jami_tur']} ta</b>",
        f"Tugagan: <b>{data['tugagan']} ta</b>",
        f"Kam qolgan: <b>{data['kam_qolgan']} ta</b>",
        f"Yetarli: <b>{data['yetarli']} ta</b>",
        "━━━━━━━━━━━━━━━━━",
    ]
    for m in data.get('mahsulotlar', []):
        lines.append(f"  • {m['nomi']}: <b>{m['qoldi']} ta</b>")
    return "\n".join(lines)


# ── KANALGA SAVDO XABARI ──────────────────────────────────────
async def send_savdo_to_channel(savdo_data: dict):
    """Har bir yangi savdoda kanalga xabar yuboriladi."""
    kanal = savdo_data.get('kanal_id') or CHANNEL_ID
    if not kanal:
        logger.warning("CHANNEL_ID sozlanmagan — kanal xabari yuborilmadi")
        return

    # To'lov turi o'zbekcha
    tolov_map = {'naqd': '💵 Naqd pul', 'plastik': '💳 Plastik karta', 'nasiya': '📋 Nasiya'}
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

    # Nasiya bo'lsa mijoz ma'lumotlari qo'shiladi
    if savdo_data['tolov_turi'] == 'nasiya' and savdo_data.get('mijoz_ism'):
        lines += [
            "",
            "👤 <b>Haridor ma'lumotlari:</b>",
            f"   Ismi: <b>{savdo_data['mijoz_ism']}</b>",
            f"   📞 Tel: {savdo_data['mijoz_tel']}",
        ]

    text = "\n".join(lines)
    try:
        await bot.send_message(kanal, text, parse_mode="HTML")
        logger.info(f"Kanal xabari yuborildi: {kanal}")
    except Exception as e:
        logger.error(f"Kanal xabari xatosi: {e}")


# ── SCHEDULER: KUNLIK HISOBOT ─────────────────────────────────
async def send_daily_report_scheduled():
    logger.info("Kunlik hisobot yuborilmoqda...")
    text = build_daily_report()
    for chat_id in ADMIN_CHAT_IDS:
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Xato {chat_id}: {e}")


# ── YORDAMCHI ─────────────────────────────────────────────────
def is_admin(chat_id: int) -> bool:
    return chat_id in ADMIN_CHAT_IDS


# ── ISHGA TUSHIRISH ───────────────────────────────────────────
async def main():
    scheduler.add_job(send_daily_report_scheduled, trigger="cron", hour=8, minute=0)
    scheduler.start()
    logger.info("Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
