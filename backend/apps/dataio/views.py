from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Price, Product
from apps.core.exceptions import DomainError
from apps.core.permissions import HasPerm, IsTenantMember
from apps.inventory.models import StockBalance, Warehouse
from apps.sales.models import Sale, SalePayment
from apps.sales.services import sales_for_user

from . import products_import
from .excel import build_workbook

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def xlsx_response(content: bytes, name: str) -> HttpResponse:
    response = HttpResponse(content, content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


class _Base(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, HasPerm]
    perm = "catalog.view"

    def get_required_perm(self, request):
        return self.perm


@extend_schema(responses={(200, XLSX): OpenApiTypes.BINARY})
class ProductTemplateView(_Base):
    perm = "catalog.manage"

    def get(self, request):
        return xlsx_response(products_import.template_bytes(request.user.tenant),
                             "mahsulotlar_shablon.xlsx")  # fmt: skip


class ImportRowSerializer(serializers.Serializer):
    line = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    action = serializers.CharField()
    errors = serializers.ListField(child=serializers.CharField())


@extend_schema(
    request=inline_serializer("ImportRequest", {
        "file": serializers.FileField(), "warehouse": serializers.IntegerField(required=False),
        "dry_run": serializers.BooleanField(required=False),
    }),
    responses=inline_serializer("ImportResult", {
        "dry_run": serializers.BooleanField(),
        "total": serializers.IntegerField(),
        "errors": serializers.IntegerField(),
        "rows": ImportRowSerializer(many=True),
        "created": serializers.IntegerField(required=False),
        "updated": serializers.IntegerField(required=False),
        "opening_document": serializers.IntegerField(required=False, allow_null=True),
    }),
)  # fmt: skip
class ProductImportView(_Base):
    perm = "catalog.manage"
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            raise DomainError("Fayl tanlanmagan", code="file_required")
        dry_run = str(request.data.get("dry_run", "true")).lower() != "false"
        tenant = request.user.tenant
        rows = products_import.parse(tenant, upload)

        needs_prices = any(r.data["prices"] for r in rows)
        needs_stock = any(r.data["opening_qty"] for r in rows)
        if needs_prices and not request.user.has_perm_code("price.edit"):
            raise DomainError("Narxlarni import qilishga ruxsat yo'q", code="permission_denied",
                              status_code=403)  # fmt: skip
        warehouse = None
        if needs_stock:
            if not request.user.has_perm_code("inventory.manage"):
                raise DomainError("Qoldiq kiritishga ruxsat yo'q", code="permission_denied",
                                  status_code=403)  # fmt: skip
            warehouse = (
                Warehouse.objects.filter(
                    tenant=tenant, pk=request.data.get("warehouse") or 0
                ).first()
                or Warehouse.objects.filter(tenant=tenant, is_active=True).first()
            )

        result = {
            "dry_run": dry_run,
            "total": len(rows),
            "errors": sum(1 for r in rows if r.errors),
            "rows": [
                {
                    "line": r.line,
                    "name": r.data.get("name", ""),
                    "sku": r.data.get("sku", ""),
                    "action": r.action,
                    "errors": r.errors,
                }
                for r in rows
            ],  # fmt: skip
        }
        if not dry_run:
            result.update(products_import.apply(tenant, request.user, rows, warehouse, request))
        return Response(result)


@extend_schema(responses={(200, XLSX): OpenApiTypes.BINARY})
class ProductExportView(_Base):
    perm = "catalog.view"

    def get(self, request):
        tenant = request.user.tenant
        products = list(
            Product.objects.filter(tenant=tenant, is_archived=False)
            .select_related("category", "base_unit").prefetch_related("barcodes")
        )  # fmt: skip
        prices = {}
        for p in Price.objects.filter(tenant=tenant).select_related("price_type"):
            prices.setdefault(p.product_id, {})[p.price_type.name] = p.amount
        pt_names = sorted({n for v in prices.values() for n in v})
        stock = {}
        for b in StockBalance.objects.filter(tenant=tenant).values("product_id", "qty"):
            stock[b["product_id"]] = stock.get(b["product_id"], 0) + b["qty"]
        headers = ["Artikul", "Nomi", "Kategoriya", "Birlik", "Valyuta", "Shtrix-kodlar",
                   "Min. qoldiq", "Qoldiq"] + [f"Narx: {n}" for n in pt_names]  # fmt: skip
        rows = [
            [p.sku, p.name, p.category.name if p.category else "", p.base_unit.short,
             p.price_currency, ", ".join(b.code for b in p.barcodes.all()), p.min_stock,
             stock.get(p.pk, 0)] + [prices.get(p.pk, {}).get(n) for n in pt_names]
            for p in products
        ]  # fmt: skip
        widths = [12, 36, 20, 8, 8, 22, 12, 12] + [14] * len(pt_names)
        name = f"mahsulotlar_{timezone.localdate():%Y%m%d}.xlsx"
        return xlsx_response(build_workbook("Mahsulotlar", headers, rows, widths), name)


@extend_schema(
    parameters=[OpenApiParameter("date_from", str), OpenApiParameter("date_to", str)],
    responses={(200, XLSX): OpenApiTypes.BINARY},
)
class SalesExportView(_Base):
    perm = "sales.create"

    def get(self, request):
        params = request.query_params
        qs = Sale.objects.filter(tenant=request.user.tenant)
        if params.get("date_from"):
            qs = qs.filter(date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(date__lte=params["date_to"])
        qs = sales_for_user(qs, request.user).select_related("customer", "cashier")
        qs = qs.prefetch_related("payments").order_by("-created_at")[:20000]
        with_cost = request.user.has_perm_code("cost.view")
        labels = dict(SalePayment.METHOD_CHOICES)
        headers = ["№", "Sana", "Mijoz", "Telefon", "Kassir", "Holat", "Summa", "Chegirma",
                   "To'lov turlari"] + (["Tannarx", "Foyda"] if with_cost else [])  # fmt: skip
        rows = []
        for s in qs:
            methods = ", ".join(f"{labels.get(p.method, p.method)}: {p.amount:,.0f}"
                                for p in s.payments.all())  # fmt: skip
            row = [s.number, timezone.localtime(s.created_at).replace(tzinfo=None),
                   s.customer.name if s.customer else "", s.customer.phone if s.customer else "",
                   s.cashier.get_full_name() or s.cashier.username,
                   "Bekor qilingan" if s.status == Sale.CANCELLED else "", s.total,
                   s.discount_total, methods]  # fmt: skip
            if with_cost:
                row += [s.cost_total, s.total - s.cost_total]
            rows.append(row)
        widths = [8, 18, 26, 16, 18, 14, 14, 12, 34, 14, 14]
        name = f"savdolar_{timezone.localdate():%Y%m%d}.xlsx"
        return xlsx_response(build_workbook("Savdolar", headers, rows, widths), name)
