from rest_framework import serializers

from .models import SETTING_DEFAULTS, Branch, Tenant


class TenantSerializer(serializers.ModelSerializer):
    effective_settings = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "inn",
            "phone",
            "address",
            "base_currency",
            "settings",
            "effective_settings",
        ]
        read_only_fields = ["id", "slug", "base_currency"]

    def get_effective_settings(self, obj: Tenant) -> dict:
        return {key: obj.get_setting(key) for key in SETTING_DEFAULTS}

    def validate_settings(self, value: dict) -> dict:
        unknown = set(value) - set(SETTING_DEFAULTS)
        if unknown:
            raise serializers.ValidationError(f"Noma'lum sozlamalar: {', '.join(sorted(unknown))}")
        if value.get("negative_stock", "forbid") not in ("forbid", "allow"):
            raise serializers.ValidationError("negative_stock: forbid yoki allow")
        if value.get("rate_source", "cbu") not in ("cbu", "manual"):
            raise serializers.ValidationError("rate_source: cbu yoki manual")
        return value


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "address", "phone", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
