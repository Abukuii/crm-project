from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import DomainError
from apps.core.views import TenantScopedMixin

from . import services
from .models import Purchase, PurchaseLine, Supplier
from .serializers import (
    PurchaseSerializer,
    StatementSerializer,
    SupplierPaymentSerializer,
    SupplierSerializer,
)


class SupplierViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    read_perm = "inventory.view"
    write_perm = "inventory.manage"
    action_perms = {"payments": "inventory.view", "statement": "inventory.view"}
    filterset_fields = ["is_archived", "currency"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = services.with_balance(super().get_queryset())
        search = self.request.query_params.get("search")
        return qs.filter(name__icontains=search) if search else qs

    @extend_schema(request=SupplierPaymentSerializer, responses=SupplierPaymentSerializer)
    @action(detail=True, methods=["get", "post"])
    def payments(self, request, pk=None):
        supplier = self.get_object()
        if request.method == "GET":
            page = self.paginate_queryset(supplier.payments.all())
            return self.get_paginated_response(SupplierPaymentSerializer(page, many=True).data)
        if not request.user.has_perm_code("finance.manage"):
            raise DomainError("To'lov kiritishga ruxsat yo'q", code="permission_denied",
                              status_code=403)  # fmt: skip
        serializer = SupplierPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.add_payment(
            tenant=self.tenant, user=request.user, supplier=supplier,
            amount=serializer.validated_data["amount"], on=serializer.validated_data.get("date"),
            note=serializer.validated_data.get("note", ""), request=request,
        )  # fmt: skip
        return Response(SupplierPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter("date_from", str), OpenApiParameter("date_to", str)],
        responses=StatementSerializer,
    )
    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        from datetime import date

        def parse(name):
            value = request.query_params.get(name)
            try:
                return date.fromisoformat(value) if value else None
            except ValueError:
                raise DomainError(f"{name}: sana noto'g'ri", code="invalid_date") from None

        data = services.statement(self.get_object(), parse("date_from"), parse("date_to"))
        return Response(StatementSerializer(data).data)


class PurchaseViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    """Kirim hujjatlari. DELETE — faqat qoralama uchun."""

    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    read_perm = "inventory.manage"
    write_perm = "inventory.manage"
    filterset_fields = ["status", "kind", "supplier", "warehouse"]
    ordering_fields = ["date", "number", "created_at"]

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("supplier", "warehouse", "created_by")
            .prefetch_related(
                Prefetch("lines", queryset=PurchaseLine.objects.select_related("product", "unit"))
            )
        )
        if getattr(self, "swagger_fake_view", False):
            return qs
        params = self.request.query_params
        if params.get("date_from"):
            qs = qs.filter(date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(date__lte=params["date_to"])
        return services.purchases_for_user(qs, self.request.user)

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Purchase.DRAFT:
            raise DomainError("Faqat qoralamani o'chirish mumkin", code="not_draft")
        instance.delete()

    @extend_schema(request=None, responses=PurchaseSerializer)
    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        purchase = services.post_purchase(
            tenant=self.tenant, user=request.user, purchase=self.get_object(), request=request
        )
        return Response(self.get_serializer(self.get_queryset().get(pk=purchase.pk)).data)

    @extend_schema(request=None, responses=PurchaseSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        purchase = services.cancel_purchase(
            tenant=self.tenant, user=request.user, purchase=self.get_object(), request=request
        )
        return Response(self.get_serializer(self.get_queryset().get(pk=purchase.pk)).data)
