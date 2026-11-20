from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import audit
from apps.core.permissions import IsTenantMember
from apps.core.views import TenantScopedMixin

from .models import Role, User
from .perms import PERMISSIONS
from .serializers import (
    PermissionItemSerializer,
    RoleSerializer,
    SetPasswordSerializer,
    SetPinSerializer,
    UserSerializer,
)


@extend_schema(responses=PermissionItemSerializer(many=True))
class PermissionListView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        return Response([{"code": c, "label": label} for c, label in PERMISSIONS.items()])


class RoleViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    read_perm = "users.manage"
    write_perm = "users.manage"

    def perform_create(self, serializer):
        role = serializer.save(tenant=self.tenant)
        audit.record(
            action="role.create",
            entity="role",
            entity_id=role.pk,
            after=serializer.data,
            request=self.request,
        )

    def perform_update(self, serializer):
        before = RoleSerializer(serializer.instance).data
        role = serializer.save()
        audit.record(
            action="role.update",
            entity="role",
            entity_id=role.pk,
            before=before,
            after=serializer.data,
            request=self.request,
        )

    def perform_destroy(self, instance):
        if instance.is_system:
            from apps.core.exceptions import DomainError

            raise DomainError("Tizim rolini o'chirib bo'lmaydi", code="system_role")
        audit.record(
            action="role.delete",
            entity="role",
            entity_id=instance.pk,
            before=RoleSerializer(instance).data,
            request=self.request,
        )
        instance.delete()


class UserViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Xodimlar. O'chirish yo'q — faqat ``is_active=false`` (tarix saqlanadi)."""

    queryset = User.objects.prefetch_related("roles", "branches")
    serializer_class = UserSerializer
    read_perm = "users.manage"
    write_perm = "users.manage"
    filterset_fields = ["is_active"]
    ordering_fields = ["username", "date_joined", "last_login"]

    def perform_create(self, serializer):
        user = serializer.save()
        audit.record(
            action="user.create",
            entity="user",
            entity_id=user.pk,
            after=serializer.data,
            request=self.request,
        )

    def perform_update(self, serializer):
        before = UserSerializer(serializer.instance, context=self.get_serializer_context()).data
        user = serializer.save()
        audit.record(
            action="user.update",
            entity="user",
            entity_id=user.pk,
            before=before,
            after=serializer.data,
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        user = self.get_object()
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        audit.record(action="user.set_password", entity="user", entity_id=user.pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="set-pin")
    def set_pin(self, request, pk=None):
        user = self.get_object()
        serializer = SetPinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_pin(serializer.validated_data["pin"] or None)
        user.save(update_fields=["pin_hash"])
        audit.record(action="user.set_pin", entity="user", entity_id=user.pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
