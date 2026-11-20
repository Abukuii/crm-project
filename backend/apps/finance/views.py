from decimal import Decimal

from django.db.models import Sum
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core import audit
from apps.core.serializers import TenantRelatedField
from apps.core.views import TenantScopedMixin
from apps.tenancy.models import Branch

from .models import Expense, ExpenseCategory


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name"]


class ExpenseSerializer(serializers.ModelSerializer):
    category = TenantRelatedField(queryset=ExpenseCategory.objects.all())
    branch = TenantRelatedField(queryset=Branch.objects.all(), allow_null=True, required=False)
    category_name = serializers.CharField(source="category.name", read_only=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = ["id", "name", "category", "category_name", "amount", "date", "branch", "note",
                  "created_by_name", "created_at"]  # fmt: skip
        read_only_fields = ["id", "created_at"]

    def get_created_by_name(self, obj) -> str | None:
        u = obj.created_by
        return (u.get_full_name() or u.username) if u else None


class ExpenseCategoryViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    read_perm = "expenses.manage"
    write_perm = "settings.manage"
    pagination_class = None


class ExpenseViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    """Xarajatlar (eski "Xarajatlar" sahifasi)."""

    queryset = Expense.objects.select_related("category", "created_by")
    serializer_class = ExpenseSerializer
    read_perm = "expenses.manage"
    write_perm = "expenses.manage"
    filterset_fields = ["category", "branch"]
    ordering_fields = ["date", "amount", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("date_from"):
            qs = qs.filter(date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(date__lte=params["date_to"])
        if params.get("search"):
            qs = qs.filter(name__icontains=params["search"])
        return qs

    def perform_create(self, serializer):
        obj = serializer.save(tenant=self.tenant, created_by=self.request.user)
        audit.record(action="expense.create", entity="expense", entity_id=obj.pk,
                     after=serializer.data, request=self.request)  # fmt: skip

    def perform_update(self, serializer):
        before = ExpenseSerializer(serializer.instance, context=self.get_serializer_context()).data
        obj = serializer.save()
        audit.record(action="expense.update", entity="expense", entity_id=obj.pk, before=before,
                     after=serializer.data, request=self.request)  # fmt: skip

    def perform_destroy(self, instance):
        audit.record(action="expense.delete", entity="expense", entity_id=instance.pk,
                     before=ExpenseSerializer(instance, context=self.get_serializer_context()).data,
                     request=self.request)  # fmt: skip
        instance.delete()

    @extend_schema(responses=inline_serializer("ExpenseTotal", {
        "total": serializers.DecimalField(max_digits=18, decimal_places=2),
        "count": serializers.IntegerField(),
    }))  # fmt: skip
    @action(detail=False, methods=["get"])
    def total(self, request):
        qs = self.filter_queryset(self.get_queryset())
        agg = qs.aggregate(total=Sum("amount"))
        return Response({"total": str(agg["total"] or Decimal("0.00")), "count": qs.count()})
