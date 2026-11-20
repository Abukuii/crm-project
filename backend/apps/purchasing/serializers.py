from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product, Unit
from apps.core.money import CURRENCY_CHOICES
from apps.core.serializers import TenantRelatedField
from apps.inventory.models import Warehouse

from .models import Purchase, PurchaseLine, Supplier, SupplierPayment


class SupplierSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = ["id", "name", "phone", "inn", "currency", "note", "is_archived", "balance",
                  "created_at"]  # fmt: skip
        read_only_fields = ["id", "created_at"]

    def get_balance(self, obj) -> str | None:
        if hasattr(obj, "purchased"):
            return str(obj.purchased - obj.paid)
        return None

    def validate_currency(self, value):
        if self.instance is not None and value != self.instance.currency:
            if self.instance.purchases.exists() or self.instance.payments.exists():
                raise serializers.ValidationError(
                    "Hujjatlari bor yetkazib beruvchi valyutasi o'zgarmaydi"
                )
        return value


class PurchaseLineSerializer(serializers.ModelSerializer):
    product = TenantRelatedField(queryset=Product.objects.all())
    unit = TenantRelatedField(queryset=Unit.objects.all())
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit_short = serializers.CharField(source="unit.short", read_only=True)
    qty = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    price = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))

    class Meta:
        model = PurchaseLine
        fields = ["id", "product", "product_name", "unit", "unit_short", "qty", "price", "factor",
                  "base_qty", "total", "unit_cost"]  # fmt: skip
        read_only_fields = ["id", "factor", "base_qty", "total", "unit_cost"]


class PurchaseSerializer(serializers.ModelSerializer):
    supplier = TenantRelatedField(queryset=Supplier.objects.all(), allow_null=True, required=False)
    warehouse = TenantRelatedField(queryset=Warehouse.objects.all())
    currency = serializers.ChoiceField(choices=CURRENCY_CHOICES, required=False)
    extra_costs = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0"), required=False
    )
    lines = PurchaseLineSerializer(many=True, required=False)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None,
                                          allow_null=True)  # fmt: skip
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id", "number", "kind", "status", "supplier", "supplier_name", "warehouse",
            "warehouse_name", "date", "currency", "rate", "extra_costs", "subtotal", "total_uzs",
            "note", "lines", "line_count", "created_by_name", "created_at", "posted_at",
        ]  # fmt: skip
        read_only_fields = ["id", "number", "status", "rate", "subtotal", "total_uzs",
                            "created_at", "posted_at"]  # fmt: skip

    def get_created_by_name(self, obj) -> str | None:
        u = obj.created_by
        return (u.get_full_name() or u.username) if u else None

    def get_line_count(self, obj) -> int:
        return len(obj.lines.all())

    def validate(self, attrs):
        if self.instance is not None and "kind" in attrs and attrs["kind"] != self.instance.kind:
            raise serializers.ValidationError({"kind": "Hujjat turini o'zgartirib bo'lmaydi"})
        return attrs

    def create(self, validated_data):
        from .services import save_draft

        req = self.context["request"]
        return save_draft(tenant=req.user.tenant, user=req.user, data=validated_data, request=req)

    def update(self, instance, validated_data):
        from .services import save_draft

        req = self.context["request"]
        return save_draft(tenant=req.user.tenant, user=req.user, data=validated_data,
                          instance=instance, request=req)  # fmt: skip


class SupplierPaymentSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = SupplierPayment
        fields = ["id", "amount", "date", "note", "is_cancelled", "created_at"]
        read_only_fields = ["id", "is_cancelled", "created_at"]


class StatementRowSerializer(serializers.Serializer):
    date = serializers.DateField()
    kind = serializers.CharField()
    ref = serializers.CharField()
    debit = serializers.DecimalField(max_digits=18, decimal_places=2)
    credit = serializers.DecimalField(max_digits=18, decimal_places=2)
    balance = serializers.DecimalField(max_digits=18, decimal_places=2)


class StatementSerializer(serializers.Serializer):
    supplier = serializers.CharField()
    currency = serializers.CharField()
    opening = serializers.DecimalField(max_digits=18, decimal_places=2)
    rows = StatementRowSerializer(many=True)
    debit_total = serializers.DecimalField(max_digits=18, decimal_places=2)
    credit_total = serializers.DecimalField(max_digits=18, decimal_places=2)
    closing = serializers.DecimalField(max_digits=18, decimal_places=2)
