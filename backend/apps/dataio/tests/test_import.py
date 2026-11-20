import io
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook, load_workbook

from apps.catalog.models import Category, Product
from apps.dataio.excel import parse_decimal
from apps.inventory.models import StockBalance
from apps.purchasing.models import Purchase

pytestmark = pytest.mark.django_db
URL = "/api/v1/dataio/products/import/"
HEAD = ["Nomi *", "Artikul", "Shtrix-kod", "Kategoriya", "Birlik *", "Valyuta (UZS/USD)",
        "Min. qoldiq", "Boshlang'ich qoldiq", "Tannarx (so'm, 1 birlik)", "Narx: Chakana"]  # fmt: skip


def xlsx(rows, header=HEAD):
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile("m.xlsx", buf.getvalue())


@pytest.mark.parametrize(("raw", "expected"), [
    (12500, D("12500")), ("12 500,50", D("12500.50")), ("0.8", D("0.8")), ("", None), (None, None),
])  # fmt: skip
def test_parse_decimal(raw, expected):
    assert parse_decimal(raw) == expected


def test_template_has_price_columns(owner_api):
    r = owner_api.get("/api/v1/dataio/products/template/")
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content)).active
    header = [c.value for c in ws[1]]
    assert "Narx: Chakana" in header and "Narx: Usta" in header


def test_dry_run_reports_errors_and_writes_nothing(owner_api):
    f = xlsx(
        [
            ["Sement", "", "", "", "qop", "UZS", 10, 5, None, 58000],  # tannarx yo'q
            ["", "", "", "", "dona", "", None, None, None, None],  # nomi yo'q
            ["Mix", "", "", "", "noma'lum", "", None, None, None, None],
        ]
    )
    r = owner_api.post(URL, {"file": f}, format="multipart").json()
    assert r["dry_run"] is True
    assert r["errors"] == 3
    assert "tannarx" in r["rows"][0]["errors"][0].lower()
    assert Product.objects.count() == 0


def test_apply_creates_products_categories_and_opening_stock(owner_api, tenant):
    f = xlsx(
        [
            [
                "Sement M-400",
                "S400",
                "4780000000017",
                "Sement",
                "qop",
                "UZS",
                20,
                100,
                "49 000",
                "58 000",
            ],
            ["Kabel VVG", "", "", "Elektr", "m", "USD", None, 250.5, 7500, 0.8],
        ]
    )
    r = owner_api.post(URL, {"file": f, "dry_run": "false"}, format="multipart").json()
    assert (r["created"], r["updated"], r["errors"]) == (2, 0, 0)
    cement = Product.objects.get(sku="S400")
    assert cement.category.name == "Sement"
    assert cement.prices.get().amount == D("58000")
    assert list(cement.barcodes.values_list("code", flat=True)) == ["4780000000017"]
    doc = Purchase.objects.get(number=r["opening_document"])
    assert (doc.kind, doc.status) == ("opening", "posted")
    assert StockBalance.objects.get(product=cement).qty == D("100")
    assert Category.objects.filter(tenant=tenant).count() == 2

    # qayta import: artikul bo'yicha yangilanadi
    f2 = xlsx([["Sement M-400 (yangi)", "S400", "", "", "qop", "UZS", None, None, None, 60000]])
    r2 = owner_api.post(URL, {"file": f2, "dry_run": "false"}, format="multipart").json()
    assert (r2["created"], r2["updated"]) == (0, 1)
    cement.refresh_from_db()
    assert cement.name == "Sement M-400 (yangi)"


def test_apply_refuses_when_errors(owner_api):
    f = xlsx([["", "", "", "", "qop", "", None, None, None, None]])
    r = owner_api.post(URL, {"file": f, "dry_run": "false"}, format="multipart")
    assert r.json()["error"]["code"] == "import_has_errors"


def test_bad_file(owner_api):
    f = SimpleUploadedFile("x.xlsx", b"not an excel file")
    assert (
        owner_api.post(URL, {"file": f}, format="multipart").json()["error"]["code"]
        == "invalid_file"
    )


def test_exports(owner_api, stock):
    r = owner_api.get("/api/v1/dataio/products/export/")
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.max_row == 3  # sarlavha + 2 mahsulot
    r = owner_api.get("/api/v1/dataio/sales/export/")
    assert r.status_code == 200
