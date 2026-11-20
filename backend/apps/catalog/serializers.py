from decimal import Decimal

from rest_framework import serializers

from apps.core.serializers import TenantContextMixin, TenantRelatedField

from .models import Barcode, Brand, Category, PriceHistory, PriceType, Product, Unit


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "short", "allow_fraction", "code"]


class CategorySerializer(serializers.ModelSerializer):
    parent = TenantRelatedField(queryset=Category.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "sort"]

    def validate_parent(self, parent):
        node = parent
        while node is not None:
            if self.instance is not None and node.pk == self.instance.pk:
                raise serializers.ValidationError("Kategoriya o'zining ichiga joylashtirilmaydi")
            node = node.parent
        return parent


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name"]


class PriceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceType
        fields = ["id", "name", "is_default", "sort"]


class ProductUnitSerializer(serializers.Serializer):
    """Qo'shimcha birlik: yozishda ``unit/factor/barcode``, o'qishda qo'shimcha ``unit_short``."""

    unit = TenantRelatedField(queryset=Unit.objects.all())
    unit_short = serializers.CharField(read_only=True)
    factor = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    barcode = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True
    )

    def to_representation(self, instance):
        codes = [b.code for b in instance.barcodes.all()]
        return {
            "unit": instance.unit_id,
            "unit_short": instance.unit.short,
            "factor": f"{instance.factor:.3f}",
            "barcode": codes[0] if codes else None,
        }


class PriceSerializer(serializers.Serializer):
    price_type = TenantRelatedField(queryset=PriceType.objects.all())
    price_type_name = serializers.CharField(source="price_type.name", read_only=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=0)


class BaseBarcodesField(serializers.ListField):
    """Asosiy birlik shtrix-kodlari (qo'shimcha birliklarniki ``units[].barcode`` da)."""

    child = serializers.CharField(max_length=64)

    def to_representation(self, data):
        return [b.code for b in data.all() if b.product_unit_id is None]


class ProductSerializer(TenantContextMixin, serializers.ModelSerializer):
    category = TenantRelatedField(queryset=Category.objects.all(), allow_null=True, required=False)
    brand = TenantRelatedField(queryset=Brand.objects.all(), allow_null=True, required=False)
    base_unit = TenantRelatedField(queryset=Unit.objects.all())
    sku = serializers.CharField(max_length=64, required=False, allow_blank=True)

    units = ProductUnitSerializer(many=True, required=False)
    barcodes = BaseBarcodesField(required=False)
    prices = PriceSerializer(many=True, required=False)

    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None, allow_null=True
    )
    base_unit_short = serializers.CharField(source="base_unit.short", read_only=True)
    allow_fraction = serializers.BooleanField(source="base_unit.allow_fraction", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "category",
            "category_name",
            "brand",
            "base_unit",
            "base_unit_short",
            "allow_fraction",
            "price_currency",
            "mxik_code",
            "description",
            "min_stock",
            "is_archived",
            "units",
            "barcodes",
            "prices",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    # ── tekshiruv ──
    def validate_sku(self, value):
        value = (value or "").strip()
        if value:
            qs = Product.objects.filter(tenant=self.tenant, sku=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Bu artikul band")
        return value

    def validate(self, attrs):
        base_unit = attrs.get("base_unit") or getattr(self.instance, "base_unit", None)
        units = attrs.get("units")
        if units is not None:
            unit_ids = [u["unit"].pk for u in units]
            if len(unit_ids) != len(set(unit_ids)):
                raise serializers.ValidationError({"units": "Birliklar takrorlanmasin"})
            if base_unit is not None and base_unit.pk in unit_ids:
                raise serializers.ValidationError({"units": "Asosiy birlik qo'shimcha bo'lmaydi"})

        codes = list(attrs.get("barcodes") or [])
        codes += [u["barcode"] for u in (units or []) if u.get("barcode")]
        codes = [c.strip() for c in codes]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError({"barcodes": "Shtrix-kodlar takrorlanmasin"})
        if codes:
            taken = Barcode.objects.filter(tenant=self.tenant, code__in=codes)
            if self.instance is not None:
                taken = taken.exclude(product=self.instance)
            taken = list(taken.values_list("code", flat=True))
            if taken:
                raise serializers.ValidationError(
                    {"barcodes": f"Boshqa mahsulotda bor: {', '.join(taken)}"}
                )

        prices = attrs.get("prices")
        if prices is not None:
            ids = [p["price_type"].pk for p in prices]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError({"prices": "Narx turlari takrorlanmasin"})
            if not self.user.has_perm_code("price.edit") and (self.instance is not None or prices):
                raise serializers.ValidationError({"prices": "Narxni o'zgartirishga ruxsat yo'q"})
        return attrs

    def create(self, validated_data):
        from .services import save_product

        return save_product(
            tenant=self.tenant,
            user=self.user,
            data=validated_data,
            request=self.context.get("request"),
        )

    def update(self, instance, validated_data):
        from .services import save_product

        return save_product(
            tenant=self.tenant,
            user=self.user,
            data=validated_data,
            instance=instance,
            request=self.context.get("request"),
        )


class PriceHistorySerializer(serializers.ModelSerializer):
    price_type_name = serializers.CharField(source="price_type.name", read_only=True)
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PriceHistory
        fields = [
            "id",
            "price_type",
            "price_type_name",
            "old_amount",
            "new_amount",
            "currency",
            "changed_by",
            "changed_by_name",
            "created_at",
        ]

    def get_changed_by_name(self, obj) -> str | None:
        user = obj.changed_by
        return (user.get_full_name() or user.username) if user else None
