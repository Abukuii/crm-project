"""Mahsulotlarni Excel'dan import qilish.

Ikki bosqich: ``dry_run`` — har bir qatorni tekshirib, xatolarni qaytaradi; ``apply`` — xato bo'lmasa
hammasini bitta tranzaksiyada saqlaydi (hammasi yoki hech narsa). Artikul bo'yicha mavjud mahsulot
yangilanadi, aks holda yangisi yaratiladi. Boshlang'ich qoldiq — "Boshlang'ich qoldiq" hujjati sifatida.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from openpyxl import load_workbook

from apps.catalog.models import Barcode, Category, PriceType, Product, Unit
from apps.catalog.services import save_product
from apps.core.exceptions import DomainError
from apps.core.money import USD, UZS
from apps.core.text import normalize

from .excel import build_workbook, cell_text, parse_decimal

ZERO = Decimal("0")

BASE_COLUMNS = [
    ("name", "Nomi *"),
    ("sku", "Artikul"),
    ("barcode", "Shtrix-kod"),
    ("category", "Kategoriya"),
    ("unit", "Birlik *"),
    ("currency", "Valyuta (UZS/USD)"),
    ("min_stock", "Min. qoldiq"),
    ("opening_qty", "Boshlang'ich qoldiq"),
    ("opening_cost", "Tannarx (so'm, 1 birlik)"),
]
PRICE_PREFIX = "Narx: "

INSTRUCTIONS = """
Mahsulotlarni import qilish yo'riqnomasi
* belgisi bor ustunlar majburiy.
Artikul to'ldirilgan va tizimda mavjud bo'lsa — mahsulot yangilanadi; aks holda yangi mahsulot yaratiladi.
Birlik: tizimdagi birlik nomi yoki qisqartmasi (dona, kg, m, m², m³, qop, pachka ...).
Valyuta: UZS yoki USD. Narxlar shu valyutada, asosiy birlik uchun yoziladi.
Kategoriya yo'q bo'lsa avtomatik yaratiladi.
Boshlang'ich qoldiq kiritilsa, tannarx (so'mda) ham kiritilishi shart — qoldiq tanlangan omborga kirim qilinadi.
Raqamlarda bo'shliq va vergul bo'lishi mumkin: 12 500,50
"""


@dataclass
class Row:
    line: int
    data: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    action: str = "create"  # create | update


def template_bytes(tenant) -> bytes:
    price_types = list(PriceType.objects.filter(tenant=tenant))
    headers = [h for _, h in BASE_COLUMNS] + [f"{PRICE_PREFIX}{pt.name}" for pt in price_types]
    example = ["Sement M-400 (50 kg)", "", "4780000000017", "Sement", "qop", "UZS", 20, 100, 49000]
    example += [58000 if i == 0 else None for i in range(len(price_types))]
    widths = [32, 12, 18, 20, 10, 12, 12, 14, 16] + [16] * len(price_types)
    return build_workbook("Mahsulotlar", headers, [example], widths, INSTRUCTIONS)


def _header_map(header_row, price_types: list[PriceType]) -> dict[int, str]:
    by_title = {normalize(h): key for key, h in BASE_COLUMNS}
    by_title.update({normalize(h.replace(" *", "")): key for key, h in BASE_COLUMNS})
    pt_by_name = {normalize(pt.name): pt for pt in price_types}
    mapping = {}
    for idx, raw in enumerate(header_row):
        title = cell_text(raw)
        if not title:
            continue
        if title.startswith(PRICE_PREFIX):
            pt = pt_by_name.get(normalize(title[len(PRICE_PREFIX) :]))
            if pt is not None:
                mapping[idx] = f"price:{pt.pk}"
            continue
        key = by_title.get(normalize(title))
        if key:
            mapping[idx] = key
    return mapping


def parse(tenant, fileobj) -> list[Row]:
    if getattr(fileobj, "size", 0) > settings.IMPORT_MAX_BYTES:
        raise DomainError("Fayl juda katta (5 MB gacha)", code="file_too_large")
    try:
        wb = load_workbook(fileobj, read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 — har qanday buzilgan fayl
        raise DomainError(
            "Faylni o'qib bo'lmadi. .xlsx formatida yuklang", code="invalid_file"
        ) from None
    ws = wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if header is None:
        raise DomainError("Fayl bo'sh", code="empty_file")
    price_types = list(PriceType.objects.filter(tenant=tenant))
    mapping = _header_map(header, price_types)
    if "name" not in mapping.values() or "unit" not in mapping.values():
        raise DomainError(
            "Shablon ustunlari topilmadi: 'Nomi' va 'Birlik' kerak", code="bad_header"
        )

    units = {}
    for u in Unit.objects.filter(tenant=tenant):
        units[normalize(u.name)] = u
        units[normalize(u.short)] = u
    existing_sku = {p.sku: p for p in Product.objects.filter(tenant=tenant)}
    barcode_owner = dict(Barcode.objects.filter(tenant=tenant).values_list("code", "product__sku"))

    rows: list[Row] = []
    seen_sku, seen_barcode = set(), set()
    for line_no, values in enumerate(rows_iter, start=2):
        if values is None or all(v in (None, "") for v in values):
            continue
        if len(rows) >= settings.IMPORT_MAX_ROWS:
            raise DomainError(f"Ko'pi bilan {settings.IMPORT_MAX_ROWS} qator", code="too_many_rows")
        raw = {key: values[i] if i < len(values) else None for i, key in mapping.items()}
        row = Row(line=line_no)
        d = row.data

        d["name"] = cell_text(raw.get("name"))
        if not d["name"]:
            row.errors.append("Nomi bo'sh")
        d["sku"] = cell_text(raw.get("sku"))
        if d["sku"]:
            if d["sku"] in seen_sku:
                row.errors.append(f"Artikul {d['sku']} faylda takrorlangan")
            seen_sku.add(d["sku"])
            if d["sku"] in existing_sku:
                row.action = "update"

        unit = units.get(normalize(cell_text(raw.get("unit"))))
        if unit is None:
            row.errors.append(f"Birlik topilmadi: '{cell_text(raw.get('unit'))}'")
        d["unit"] = unit

        currency = (cell_text(raw.get("currency")) or UZS).upper()
        if currency not in (UZS, USD):
            row.errors.append("Valyuta UZS yoki USD bo'lishi kerak")
        d["currency"] = currency

        d["category"] = cell_text(raw.get("category"))
        d["barcode"] = cell_text(raw.get("barcode"))
        if d["barcode"]:
            if d["barcode"] in seen_barcode:
                row.errors.append(f"Shtrix-kod {d['barcode']} faylda takrorlangan")
            seen_barcode.add(d["barcode"])
            owner = barcode_owner.get(d["barcode"])
            if owner is not None and owner != d["sku"]:
                row.errors.append(f"Shtrix-kod {d['barcode']} boshqa mahsulotda (artikul {owner})")

        def number(key, label, *, positive=False, d=d, row=row, raw=raw):
            try:
                value = parse_decimal(raw.get(key))
            except ValueError as exc:
                row.errors.append(f"{label}: {exc}")
                return None
            if value is not None and (value < 0 or (positive and value == 0)):
                row.errors.append(f"{label} manfiy bo'lmasin")
                return None
            return value

        d["min_stock"] = number("min_stock", "Min. qoldiq")
        d["opening_qty"] = number("opening_qty", "Boshlang'ich qoldiq")
        d["opening_cost"] = number("opening_cost", "Tannarx")
        if d["opening_qty"] and d["opening_cost"] is None:
            row.errors.append("Boshlang'ich qoldiq uchun tannarx kiriting")
        if d["opening_qty"] and unit is not None and not unit.allow_fraction:
            if d["opening_qty"] != d["opening_qty"].to_integral_value():
                row.errors.append(f"'{unit.short}' birligida qoldiq butun son bo'lishi kerak")

        d["prices"] = {}
        for key in mapping.values():
            if key.startswith("price:"):
                pt_id = int(key.split(":")[1])
                value = number(key, "Narx")
                if value is not None:
                    d["prices"][pt_id] = value
        rows.append(row)

    if not rows:
        raise DomainError("Faylda mahsulot qatori yo'q", code="empty_file")
    return rows


@transaction.atomic
def apply(tenant, user, rows: list[Row], warehouse, request=None) -> dict:
    from apps.purchasing.models import Purchase
    from apps.purchasing.services import post_purchase, save_draft

    if any(r.errors for r in rows):
        raise DomainError("Faylda xatolar bor", code="import_has_errors")
    price_types = {pt.pk: pt for pt in PriceType.objects.filter(tenant=tenant)}
    categories = {normalize(c.name): c for c in Category.objects.filter(tenant=tenant, parent=None)}
    existing = {p.sku: p for p in Product.objects.filter(tenant=tenant)}
    created = updated = 0
    opening_lines = []

    for row in rows:
        d = row.data
        category = None
        if d["category"]:
            key = normalize(d["category"])
            category = categories.get(key)
            if category is None:
                category = Category.objects.create(tenant=tenant, name=d["category"])
                categories[key] = category
        instance = existing.get(d["sku"]) if d["sku"] else None
        data = {"name": d["name"], "base_unit": d["unit"], "price_currency": d["currency"]}
        if d["sku"]:
            data["sku"] = d["sku"]
        if category is not None:
            data["category"] = category
        if d["min_stock"] is not None:
            data["min_stock"] = d["min_stock"]
        if d["prices"]:
            data["prices"] = [
                {"price_type": price_types[k], "amount": v} for k, v in d["prices"].items()
            ]
        if d["barcode"]:
            current = []
            if instance is not None:
                current = list(instance.barcodes.filter(product_unit__isnull=True)
                               .values_list("code", flat=True))  # fmt: skip
            if d["barcode"] not in current:
                data["barcodes"] = [*current, d["barcode"]]
        product = save_product(
            tenant=tenant, user=user, data=data, instance=instance, request=request
        )
        if instance is None:
            created += 1
        else:
            updated += 1
        if d["opening_qty"]:
            opening_lines.append({"product": product, "unit": product.base_unit,
                                  "qty": d["opening_qty"], "price": d["opening_cost"]})  # fmt: skip

    opening_number = None
    if opening_lines:
        doc = save_draft(tenant=tenant, user=user, request=request, data={
            "kind": Purchase.KIND_OPENING, "warehouse": warehouse, "currency": UZS,
            "note": "Excel import", "lines": opening_lines,
        })  # fmt: skip
        post_purchase(tenant=tenant, user=user, purchase=doc, request=request)
        opening_number = doc.number
    return {"created": created, "updated": updated, "opening_document": opening_number}
