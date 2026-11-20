"""Excel yordamchilari: qiymatlarni o'qish va chiroyli varaq yaratish."""

import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BRAND = "EA580C"
_SPACES = re.compile(r"[\s  ]")


def parse_decimal(value) -> Decimal | None:
    """Excel qiymatini Decimal'ga: 12500, "12 500,50", "12500.5" → Decimal; bo'sh → None."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("raqam emas")
    if isinstance(value, int | float):
        return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
    text = _SPACES.sub("", str(value))
    if not text:
        return None
    if text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"'{value}' raqam emas") from None


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # shtrix-kod/artikul 4.78e12 bo'lib qolmasin
    return str(value).strip()


def build_workbook(title: str, headers: list[str], rows: list[list], widths: list[int] | None = None,
                   note: str | None = None) -> bytes:  # fmt: skip
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    for i, _ in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=BRAND)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    for row in rows:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in row])
    for i, h in enumerate(headers, start=1):
        width = widths[i - 1] if widths and i <= len(widths) else max(12, min(40, len(h) + 4))
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, datetime | date):
                c.number_format = (
                    "DD.MM.YYYY HH:MM" if isinstance(c.value, datetime) else "DD.MM.YYYY"
                )
            elif isinstance(c.value, float | int) and not isinstance(c.value, bool):
                c.number_format = "#,##0.##"
    if note:
        info = wb.create_sheet("Yo'riqnoma")
        for line in note.strip().splitlines():
            info.append([line])
        info.column_dimensions["A"].width = 110
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
