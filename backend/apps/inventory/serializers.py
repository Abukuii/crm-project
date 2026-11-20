from rest_framework import serializers

from apps.core.money import q_money
from apps.core.serializers import TenantRelatedField
from apps.tenancy.models import Branch

from .models import StockBalance, StockMove, Warehouse


class CostHidingMixin:
    """``cost.view`` ruxsati bo'lmasa tannarx maydonlari javobdan olib tashlanadi."""

    cost_fields: tuple[str, ...] = ()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request is not None and not request.user.has_perm_code("cost.view"):
            for field in self.cost_fields:
                data.pop(field, None)
        return data


class WarehouseSerializer(serializers.ModelSerializer):
    branch = TenantRelatedField(queryset=Branch.objects.all())
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Warehouse
        fields = ["id", "name", "branch", "branch_name", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class StockBalanceSerializer(CostHidingMixin, serializers.ModelSerializer):
    cost_fields = ("avg_cost", "total_cost")

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    unit = serializers.CharField(source="product.base_unit.short", read_only=True)
    min_stock = serializers.DecimalField(
        source="product.min_stock", max_digits=14, decimal_places=3, read_only=True
    )
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    total_cost = serializers.SerializerMethodField()

    class Meta:
        model = StockBalance
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "product",
            "product_name",
            "product_sku",
            "unit",
            "qty",
            "reserved",
            "min_stock",
            "avg_cost",
            "total_cost",
            "updated_at",
        ]

    def get_total_cost(self, obj) -> str:
        return str(q_money(obj.qty * obj.avg_cost))


class StockMoveSerializer(CostHidingMixin, serializers.ModelSerializer):
    cost_fields = ("unit_cost",)

    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMove
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "product",
            "product_name",
            "qty",
            "unit_cost",
            "qty_after",
            "doc_type",
            "doc_id",
            "note",
            "created_by",
            "created_by_name",
            "created_at",
        ]

    def get_created_by_name(self, obj) -> str | None:
        user = obj.created_by
        return (user.get_full_name() or user.username) if user else None
