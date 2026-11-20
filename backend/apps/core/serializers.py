from rest_framework import serializers


class TenantRelatedField(serializers.PrimaryKeyRelatedField):
    """FK maydoni: faqat joriy tenant'ning yozuvlarini qabul qiladi (IDOR'dan himoya)."""

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return queryset.none()
        return queryset.filter(tenant_id=request.user.tenant_id)


class TenantContextMixin:
    @property
    def tenant(self):
        return self.context["request"].user.tenant

    @property
    def user(self):
        return self.context["request"].user
