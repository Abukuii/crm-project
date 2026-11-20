from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import HasPerm, IsTenantMember


class TenantScopedMixin:
    """Barcha tenant ma'lumotlari uchun asosiy mixin.

    * queryset faqat joriy foydalanuvchi tenant'i bo'yicha;
    * yangi yozuvga tenant avtomatik qo'yiladi;
    * ``read_perm`` / ``write_perm`` / ``action_perms`` orqali ruxsatlar.
    """

    permission_classes = [IsAuthenticated, IsTenantMember, HasPerm]
    read_perm: str | None = None
    write_perm: str | None = None
    action_perms: dict[str, str] = {}

    def get_required_perm(self, request) -> str | None:
        action = getattr(self, "action", None)
        if action in self.action_perms:
            return self.action_perms[action]
        return self.read_perm if request.method in SAFE_METHODS else self.write_perm

    @property
    def tenant(self):
        return self.request.user.tenant

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI generatsiyasi
            return super().get_queryset().none()
        return super().get_queryset().filter(tenant_id=self.request.user.tenant_id)

    def perform_create(self, serializer):
        serializer.save(tenant=self.tenant)


@extend_schema(
    responses=inline_serializer(
        "Health", {"status": serializers.CharField(), "db": serializers.BooleanField()}
    )
)
class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_ok = True
        except Exception:  # noqa: BLE001
            db_ok = False
        return Response(
            {"status": "ok" if db_ok else "degraded", "db": db_ok}, status=200 if db_ok else 503
        )
