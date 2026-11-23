from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.models import PriceType, Product, Unit
from apps.core.money import q_money, q_qty
from apps.core.serializers import TenantRelatedField
from apps.inventory.models import Warehouse

from .models import (
    CashMovement,
    Customer,
    CustomerPayment,
    Receivable,
    Sale,
    SaleLine,
    SalePayment,
    SaleReturn,
    Shift,
)

D0 = Decimal("0")


class CustomerSerializer(serializers.ModelSerializer):
    price_type = TenantRelatedField(queryset=PriceType.objects.all(), allow_null=True,
                                    required=False)  # fmt: skip
    debt = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True, default=None,
                                    allow_null=True)  # fmt: skip
    overdue_debt = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True,
                                            default=None, allow_null=True)  # fmt: skip

    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "address", "kind", "inn", "price_type", "credit_limit",
                  "payment_days", "note", "is_archived", "debt", "overdue_debt", "created_at"]  # fmt: skip
        read_only_fields = ["id", "created_at"]

    def validate_phone(self, value):
        value = "".join(ch for ch in value if ch.isdigit() or ch == "+")
        if value:
            qs = Customer.objects.filter(tenant=self.context["request"].user.tenant, phone=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Bu telefon raqamli mijoz mavjud")
        return value


class SaleItemInSerializer(serializers.Serializer):
    product = TenantRelatedField(queryset=Product.objects.select_related("base_unit"))
    unit = TenantRelatedField(queryset=Unit.objects.all(), required=False)
    qty = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    price = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"),
                                     required=False, allow_null=True)  # fmt: skip


class PaymentInSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=SalePayment.METHOD_CHOICES)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=D0)


class SaleCreateSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    warehouse = TenantRelatedField(queryset=Warehouse.objects.select_related("branch"))
    customer = TenantRelatedField(queryset=Customer.objects.select_related("price_type"),
                                  required=False, allow_null=True)  # fmt: skip
    items = SaleItemInSerializer(many=True)
    payments = PaymentInSerializer(many=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True)


class SaleLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit_short = serializers.CharField(source="unit.short", read_only=True)
    returned_qty = serializers.SerializerMethodField()

    class Meta:
        model = SaleLine
        fields = ["id", "product", "product_name", "unit", "unit_short", "qty", "list_price",
                  "price", "discount", "total", "cost_total", "returned_qty"]  # fmt: skip

    def get_returned_qty(self, obj) -> str:
        active = (r.qty for r in obj.returned.all() if r.sale_return.status == "posted")
        return str(q_qty(sum(active, D0)))


class SalePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalePayment
        fields = ["method", "amount"]


class SaleSerializer(serializers.ModelSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)
    payments = SalePaymentSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True, default=None,
                                          allow_null=True)  # fmt: skip
    customer_phone = serializers.CharField(source="customer.phone", read_only=True, default=None,
                                           allow_null=True)  # fmt: skip
    cashier_name = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    profit = serializers.SerializerMethodField()
    returns = serializers.SerializerMethodField()
    returned_total = serializers.SerializerMethodField()
    shift_number = serializers.IntegerField(source="shift.number", read_only=True, default=None,
                                            allow_null=True)  # fmt: skip

    class Meta:
        model = Sale
        fields = ["id", "number", "date", "created_at", "status", "warehouse", "warehouse_name",
                  "cashier", "cashier_name", "customer", "customer_name", "customer_phone",
                  "subtotal", "discount_total", "total", "cost_total", "profit", "note", "lines",
                  "payments", "cancelled_at", "cancel_reason", "returns", "returned_total",
                  "shift_number"]  # fmt: skip

    def get_returned_total(self, obj) -> str:
        return str(q_money(sum((r.total for r in obj.returns.all() if r.status == "posted"), D0)))

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_returns(self, obj) -> list[dict]:
        return SaleReturnBriefSerializer(obj.returns.all(), many=True).data

    def get_cashier_name(self, obj) -> str:
        return obj.cashier.get_full_name() or obj.cashier.username

    def get_profit(self, obj) -> str:
        returned = sum(
            (r.total - r.cost_total for r in obj.returns.all() if r.status == "posted"), D0
        )
        return str(obj.total - obj.cost_total - returned)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request is not None and not request.user.has_perm_code("cost.view"):
            data.pop("cost_total", None)
            data.pop("profit", None)
            for line in data.get("lines", []):
                line.pop("cost_total", None)
        return data


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)


class SalesSummarySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=18, decimal_places=2)
    discount = serializers.DecimalField(max_digits=18, decimal_places=2)
    returns = serializers.DecimalField(max_digits=18, decimal_places=2)
    profit = serializers.DecimalField(max_digits=18, decimal_places=2, allow_null=True)
    by_method = serializers.DictField(
        child=serializers.DecimalField(max_digits=18, decimal_places=2)
    )


class ReceivableSerializer(serializers.ModelSerializer):
    sale_number = serializers.IntegerField(source="sale.number", read_only=True)
    sale_date = serializers.DateField(source="sale.date", read_only=True)
    remaining = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Receivable
        fields = ["id", "sale", "sale_number", "sale_date", "amount", "paid", "remaining",
                  "due_date", "status", "is_overdue"]  # fmt: skip

    def get_is_overdue(self, obj) -> bool:
        from django.utils import timezone

        return obj.status == Receivable.OPEN and obj.due_date < timezone.localdate()


class CustomerPaymentSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    receivable = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerPayment
        fields = ["id", "amount", "method", "date", "note", "receivable", "created_by_name",
                  "created_at"]  # fmt: skip
        read_only_fields = ["id", "date", "created_at"]

    def get_created_by_name(self, obj) -> str | None:
        u = obj.created_by
        return (u.get_full_name() or u.username) if u else None


class PosUnitSerializer(serializers.Serializer):
    unit = serializers.IntegerField()
    unit_short = serializers.CharField()
    factor = serializers.DecimalField(max_digits=14, decimal_places=3)
    price = serializers.DecimalField(max_digits=18, decimal_places=2)
    barcodes = serializers.ListField(child=serializers.CharField())  # shu birlik shtrix-kodlari


class PosProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    barcodes = serializers.ListField(child=serializers.CharField())
    category = serializers.CharField(allow_null=True)
    allow_fraction = serializers.BooleanField()
    stock = serializers.DecimalField(max_digits=14, decimal_places=3)
    units = PosUnitSerializer(many=True)  # birinchisi — asosiy birlik


# ── Qaytarish ────────────────────────────────────────────────────────────────
class SaleReturnBriefSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SaleReturn
        fields = ["id", "number", "date", "refund_method", "total", "reason", "created_by_name",
                  "created_at", "status", "cancelled_at", "cancel_reason",
                  "cancelled_by_name"]  # fmt: skip

    def get_cancelled_by_name(self, obj) -> str | None:
        u = obj.cancelled_by
        return (u.get_full_name() or u.username) if u else None

    def get_created_by_name(self, obj) -> str | None:
        u = obj.created_by
        return (u.get_full_name() or u.username) if u else None


class ReturnItemSerializer(serializers.Serializer):
    line = serializers.IntegerField()
    qty = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class ReturnCreateSerializer(serializers.Serializer):
    items = ReturnItemSerializer(many=True)
    refund_method = serializers.ChoiceField(choices=SaleReturn.REFUND_CHOICES)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)


# ── Smena ────────────────────────────────────────────────────────────────────
class ShiftSerializer(serializers.ModelSerializer):
    cashier_name = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Shift
        fields = ["id", "number", "status", "warehouse", "warehouse_name", "cashier",
                  "cashier_name", "opened_at", "closed_at", "opening_cash", "expected_cash",
                  "counted_cash", "difference", "note"]  # fmt: skip

    def get_cashier_name(self, obj) -> str:
        return obj.cashier.get_full_name() or obj.cashier.username


class ShiftOpenSerializer(serializers.Serializer):
    warehouse = TenantRelatedField(queryset=Warehouse.objects.select_related("branch"))
    opening_cash = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=D0)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True)


class CashMoveSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = CashMovement
        fields = ["id", "kind", "amount", "note", "created_at"]
        read_only_fields = ["id", "created_at"]


class ShiftCloseSerializer(serializers.Serializer):
    counted_cash = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=D0)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True)


_M = {"max_digits": 18, "decimal_places": 2}


class ShiftReportSerializer(serializers.Serializer):
    shift = serializers.IntegerField()
    cashier = serializers.CharField()
    opened_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    opening_cash = serializers.DecimalField(**_M)
    sales_count = serializers.IntegerField()
    sales_total = serializers.DecimalField(**_M)
    discount_total = serializers.DecimalField(**_M)
    cancelled_count = serializers.IntegerField()
    by_method = serializers.DictField(child=serializers.DecimalField(**_M))
    returns_count = serializers.IntegerField()
    returns_total = serializers.DecimalField(**_M)
    refunds_by_method = serializers.DictField(child=serializers.DecimalField(**_M))
    returns_cancelled_count = serializers.IntegerField(required=False)
    returns_cancelled_total = serializers.DecimalField(**_M, required=False)
    cancelled_refunds_by_method = serializers.DictField(
        child=serializers.DecimalField(**_M), required=False
    )
    net_revenue = serializers.DecimalField(**_M)
    debt_payments = serializers.DictField(child=serializers.DecimalField(**_M))
    cash_in = serializers.DecimalField(**_M)
    cash_out = serializers.DecimalField(**_M)
    expected_cash = serializers.DecimalField(**_M)
    counted_cash = serializers.DecimalField(**_M, required=False)
    difference = serializers.DecimalField(**_M, required=False)
