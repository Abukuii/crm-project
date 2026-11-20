from rest_framework import mixins, viewsets
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from apps.core import audit
from apps.core.permissions import HasPerm, IsTenantMember
from apps.core.views import TenantScopedMixin

from .models import Branch
from .serializers import BranchSerializer, TenantSerializer


class CurrentTenantView(RetrieveUpdateAPIView):
    """GET/PATCH /tenancy/current/ — joriy biznes rekvizitlari va sozlamalari."""

    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsTenantMember, HasPerm]

    def get_required_perm(self, request):
        return None if request.method == "GET" else "settings.manage"

    def get_object(self):
        return self.request.user.tenant

    def perform_update(self, serializer):
        before = TenantSerializer(serializer.instance).data
        tenant = serializer.save()
        audit.record(
            action="tenant.update",
            entity="tenant",
            entity_id=tenant.pk,
            before=before,
            after=serializer.data,
            request=self.request,
        )


class BranchViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    write_perm = "settings.manage"
    filterset_fields = ["is_active"]
