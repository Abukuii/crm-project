import django_filters
from django.db.models import F
from rest_framework import mixins, viewsets

from apps.core.text import normalize
from apps.core.views import TenantScopedMixin

from .models import StockBalance, StockMove, Warehouse
from .serializers import StockBalanceSerializer, StockMoveSerializer, WarehouseSerializer


class BranchScopedMixin:
    """Foydalanuvchi faqat o'ziga ruxsat etilgan filial omborlarini ko'radi."""

    branch_lookup = "warehouse__branch_id"

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return qs
        allowed = self.request.user.allowed_branch_ids()
        return qs if allowed is None else qs.filter(**{f"{self.branch_lookup}__in": allowed})


class WarehouseViewSet(
    BranchScopedMixin,
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Warehouse.objects.select_related("branch")
    serializer_class = WarehouseSerializer
    read_perm = "inventory.view"
    write_perm = "settings.manage"
    branch_lookup = "branch_id"
    filterset_fields = ["branch", "is_active"]
    pagination_class = None


class BalanceFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    low_stock = django_filters.BooleanFilter(method="filter_low_stock")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = StockBalance
        fields = ["warehouse", "product"]

    def filter_search(self, qs, name, value):
        for word in normalize(value).split():
            qs = qs.filter(product__search_text__contains=word)
        return qs

    def filter_low_stock(self, qs, name, value):
        return qs.filter(qty__lte=F("product__min_stock")) if value else qs

    def filter_in_stock(self, qs, name, value):
        return qs.filter(qty__gt=0) if value else qs.filter(qty__lte=0)


class StockBalanceViewSet(BranchScopedMixin, TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StockBalance.objects.select_related("product__base_unit", "warehouse")
    serializer_class = StockBalanceSerializer
    read_perm = "inventory.view"
    filterset_class = BalanceFilter
    ordering_fields = ["qty", "product__name", "updated_at"]
    ordering = ["product__name"]


class StockMoveViewSet(BranchScopedMixin, TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StockMove.objects.select_related("product", "warehouse", "created_by")
    serializer_class = StockMoveSerializer
    read_perm = "inventory.view"
    filterset_fields = ["warehouse", "product", "doc_type", "doc_id"]
    ordering_fields = ["created_at"]
