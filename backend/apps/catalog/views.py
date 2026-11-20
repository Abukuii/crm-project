from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core import audit
from apps.core.exceptions import DomainError
from apps.core.views import TenantScopedMixin

from .filters import ProductFilter
from .models import Barcode, Brand, Category, Price, PriceType, Product, ProductUnit, Unit
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    PriceHistorySerializer,
    PriceTypeSerializer,
    ProductSerializer,
    UnitSerializer,
)


class CatalogDictViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    read_perm = "catalog.view"
    write_perm = "catalog.manage"
    pagination_class = None  # ma'lumotnomalar kichik — to'liq qaytariladi


class UnitViewSet(CatalogDictViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer


class CategoryViewSet(CatalogDictViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class BrandViewSet(CatalogDictViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


class PriceTypeViewSet(CatalogDictViewSet):
    queryset = PriceType.objects.all()
    serializer_class = PriceTypeSerializer
    write_perm = "settings.manage"

    def perform_create(self, serializer):
        obj = serializer.save(tenant=self.tenant)
        self._ensure_single_default(obj)

    def perform_update(self, serializer):
        self._ensure_single_default(serializer.save())

    def _ensure_single_default(self, obj):
        if obj.is_default:
            PriceType.objects.filter(tenant=obj.tenant, is_default=True).exclude(pk=obj.pk).update(
                is_default=False
            )


class ProductViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    """Mahsulotlar. DELETE — arxivlash (yozuv o'chirilmaydi)."""

    serializer_class = ProductSerializer
    read_perm = "catalog.view"
    write_perm = "catalog.manage"
    filterset_class = ProductFilter
    ordering_fields = ["name", "sku", "created_at", "updated_at"]
    action_perms = {"price_history": "catalog.view"}

    queryset = Product.objects.all()

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("category", "base_unit", "brand")
            .prefetch_related(
                Prefetch(
                    "units",
                    queryset=ProductUnit.objects.select_related("unit").prefetch_related(
                        "barcodes"
                    ),
                ),
                "barcodes",
                Prefetch("prices", queryset=Price.objects.select_related("price_type")),
            )
        )

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.save(update_fields=["is_archived", "updated_at"])
        audit.record(
            action="product.archive", entity="product", entity_id=instance.pk, request=self.request
        )

    @extend_schema(parameters=[OpenApiParameter("code", str, required=True)])
    @action(detail=False, methods=["get"], url_path="by-barcode")
    def by_barcode(self, request):
        """Kassa skaneri uchun: shtrix-kod → mahsulot + birlik koeffitsienti."""
        code = (request.query_params.get("code") or "").strip()
        barcode = (
            Barcode.objects.filter(tenant_id=request.user.tenant_id, code=code)
            .select_related("product_unit__unit")
            .first()
        )
        if barcode is None:
            raise DomainError("Shtrix-kod topilmadi", code="barcode_not_found", status_code=404)
        product = self.get_queryset().get(pk=barcode.product_id)
        pu = barcode.product_unit
        return Response(
            {
                "product": ProductSerializer(product, context=self.get_serializer_context()).data,
                "unit": pu.unit_id if pu else product.base_unit_id,
                "factor": str(pu.factor) if pu else "1.000",
            }
        )

    @action(detail=True, methods=["get"], url_path="price-history")
    def price_history(self, request, pk=None):
        product = self.get_object()
        page = self.paginate_queryset(
            product.price_history.select_related("price_type", "changed_by")
        )
        return self.get_paginated_response(PriceHistorySerializer(page, many=True).data)
