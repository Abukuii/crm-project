import psycopg2
import os
from datetime import date

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )


def get_daily_report() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    bugun = date.today().isoformat()

    cur.execute("""
        SELECT
            COUNT(*) as soni,
            COALESCE(SUM(CASE WHEN tolov_turi='naqd' THEN jami_summa ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN tolov_turi='plastik' THEN jami_summa ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN tolov_turi='nasiya' THEN jami_summa ELSE 0 END), 0),
            COALESCE(SUM(jami_summa), 0)
        FROM crm_savdo WHERE sana = %s
    """, (bugun,))
    row = cur.fetchone()

    if not row or row[0] == 0:
        conn.close()
        return {}

    cur.execute("""
        SELECT m.nomi, SUM(si.soni) as jami_son
        FROM crm_savdoitem si
        JOIN crm_mahsulot m ON si.mahsulot_id = m.id
        JOIN crm_savdo s ON si.savdo_id = s.id
        WHERE s.sana = %s
        GROUP BY m.id ORDER BY jami_son DESC LIMIT 3
    """, (bugun,))
    top = [{"nomi": r[0], "soni": r[1]} for r in cur.fetchall()]

    cur.execute("SELECT COUNT(*) FROM crm_savdo WHERE sana=%s AND tolov_turi='nasiya'", (bugun,))
    yangi_nasiya = cur.fetchone()[0]
    conn.close()

    return {
        "sana": date.today().strftime("%d.%m.%Y"),
        "savdolar_soni": row[0],
        "naqd": int(row[1]),
        "plastik": int(row[2]),
        "nasiya": int(row[3]),
        "jami": int(row[4]),
        "top_mahsulotlar": top,
        "yangi_qarzdorlar": yangi_nasiya,
    }


def get_monthly_stats() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    bugun = date.today()
    oy_boshi = bugun.replace(day=1).isoformat()

    cur.execute("""
        SELECT COUNT(*),
            COALESCE(SUM(jami_summa), 0),
            COALESCE(SUM(CASE WHEN tolov_turi='nasiya' THEN jami_summa ELSE 0 END), 0)
        FROM crm_savdo WHERE sana >= %s
    """, (oy_boshi,))
    row = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM crm_mijoz WHERE DATE(yaratilgan) >= %s", (oy_boshi,))
    yangi_mijozlar = cur.fetchone()[0]

    cur.execute("""
        SELECT m.nomi, SUM(si.soni) as jami_son
        FROM crm_savdoitem si
        JOIN crm_mahsulot m ON si.mahsulot_id = m.id
        JOIN crm_savdo s ON si.savdo_id = s.id
        WHERE s.sana >= %s
        GROUP BY m.id ORDER BY jami_son DESC LIMIT 1
    """, (oy_boshi,))
    top = cur.fetchone()
    conn.close()

    return {
        "oy": bugun.strftime("%B %Y"),
        "savdolar_soni": row[0],
        "jami_daromad": int(row[1]),
        "nasiya_jami": int(row[2]),
        "yangi_mijozlar": yangi_mijozlar,
        "top_mahsulot": f"{top[0]} ({top[1]} ta)" if top else "—",
    }


def get_qarzdorlar() -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT mj.ism_familiya, mj.telefon,
            COALESCE(SUM(s.jami_summa), 0) as jami_qarz
        FROM crm_mijoz mj
        JOIN crm_savdo s ON s.mijoz_id = mj.id
        WHERE s.to_langan = False
        GROUP BY mj.id ORDER BY jami_qarz DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"ism": r[0], "telefon": r[1], "qarz": int(r[2])} for r in rows]


def get_kam_qolganlar(chegara: int = 20) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nomi, qoldi FROM crm_mahsulot WHERE qoldi <= %s ORDER BY qoldi", (chegara,))
    rows = cur.fetchall()
    conn.close()
    return [{"nomi": r[0], "qoldi": r[1]} for r in rows]


def get_mahsulotlar_soni() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) as jami,
            SUM(CASE WHEN qoldi = 0 THEN 1 ELSE 0 END) as tugagan,
            SUM(CASE WHEN qoldi > 0 AND qoldi <= 10 THEN 1 ELSE 0 END) as kam,
            SUM(CASE WHEN qoldi > 10 THEN 1 ELSE 0 END) as yetarli
        FROM crm_mahsulot
    """)
    row = cur.fetchone()

    cur.execute("SELECT nomi, qoldi FROM crm_mahsulot ORDER BY qoldi LIMIT 15")
    mahsulotlar = [{"nomi": r[0], "qoldi": r[1]} for r in cur.fetchall()]
    conn.close()

    return {
        "jami_tur": row[0] or 0,
        "tugagan": row[1] or 0,
        "kam_qolgan": row[2] or 0,
        "yetarli": row[3] or 0,
        "mahsulotlar": mahsulotlar,
    }
