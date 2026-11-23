"""Excel yordamchilari: qiymatlarni o'qish va chiroyli varaq yaratish."""

import io
import re
from dataclasses import dataclass, field
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


@dataclass
class Sheet:
    title: str
    headers: list[str]
    rows: list[list]
    widths: list[int] | None = None
    # Jami qatori (qalin), masalan ["Jami", None, 1200, ...]
    footer: list | None = None
    notes: list[str] = field(default_factory=list)


def _fill_sheet(ws, sheet: Sheet) -> None:
    ws.title = sheet.title[:31]
    start_row = 1
    for note in sheet.notes:
        ws.append([note])
        ws.cell(row=start_row, column=1).font = Font(
            bold=start_row == 1, size=13 if start_row == 1 else 11
        )
        start_row += 1
    if sheet.notes:
        ws.append([])
        start_row += 1
    ws.append(sheet.headers)
    for i, _ in enumerate(sheet.headers, start=1):
        c = ws.cell(row=start_row, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=BRAND)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[start_row].height = 30
    ws.freeze_panes = f"A{start_row + 1}"  # ws.cell() bo'sh qator yaratib qo'yardi
    for row in sheet.rows:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in row])
    if sheet.footer:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in sheet.footer])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="FFEDD5")
    for i, h in enumerate(sheet.headers, start=1):
        width = (
            sheet.widths[i - 1]
            if sheet.widths and i <= len(sheet.widths)
            else max(12, min(40, len(h) + 4))
        )
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=start_row + 1):
        for c in row:
            if isinstance(c.value, datetime | date):
                c.number_format = (
                    "DD.MM.YYYY HH:MM" if isinstance(c.value, datetime) else "DD.MM.YYYY"
                )
            elif isinstance(c.value, float | int) and not isinstance(c.value, bool):
                c.number_format = "#,##0.##"


def build_sheets(sheets: list[Sheet]) -> bytes:
    """Bir nechta varaqli Excel fayl."""
    wb = Workbook()
    for i, sheet in enumerate(sheets):
        _fill_sheet(wb.active if i == 0 else wb.create_sheet(), sheet)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_workbook(
    title: str,
    headers: list[str],
    rows: list[list],
    widths: list[int] | None = None,
    note: str | None = None,
) -> bytes:
    sheets = [Sheet(title, headers, rows, widths)]
    wb = Workbook()
    _fill_sheet(wb.active, sheets[0])
    if note:
        info = wb.create_sheet("Yo'riqnoma")
        for line in note.strip().splitlines():
            info.append([line])
        info.column_dimensions["A"].width = 110
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
