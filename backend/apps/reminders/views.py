from rest_framework import serializers, viewsets
from rest_framework.routers import SimpleRouter

from apps.core.views import TenantScopedMixin

from .models import Reminder


class ReminderSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Reminder
        fields = ["id", "text", "level", "due_date", "is_done", "created_by_name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_created_by_name(self, obj) -> str | None:
        u = obj.created_by
        return (u.get_full_name() or u.username) if u else None


class ReminderViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Reminder.objects.select_related("created_by")
    serializer_class = ReminderSerializer
    read_perm = "reminders.manage"
    write_perm = "reminders.manage"
    filterset_fields = ["is_done", "level"]
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(tenant=self.tenant, created_by=self.request.user)


router = SimpleRouter()
router.register("reminders", ReminderViewSet, basename="reminder")
urlpatterns = router.urls
