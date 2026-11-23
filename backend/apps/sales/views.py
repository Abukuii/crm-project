from decimal import Decimal

from django.db.models import Count, Prefetch, Q, Sum
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog.filters import ProductFilter
from apps.catalog.models import Product, ProductUnit
from apps.core.exceptions import DomainError
from apps.core.money import USD
from apps.core.views import TenantScopedMixin
from apps.currency.services import RateNotFound, get_rate
from apps.inventory.models import StockBalance, Warehouse

from . import services
from .models import Customer, Receivable, Sale, SaleLine, SalePayment
from .serializers import (
    CancelSerializer,
    CustomerPaymentSerializer,
    CustomerSerializer,
    PosProductSerializer,
    ReceivableSerializer,
    SaleCreateSerializer,
    SaleSerializer,
    SalesSummarySerializer,
)

ZERO = Decimal("0")


class CustomerViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Mijozlar. ``?has_debt=true`` — qarzdorlar ro'yxati (eski "Qarzdorlar" sahifasi)."""

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    read_perm = "customers.view"
    write_perm = "customers.manage"
    action_perms = {"receivables": "customers.view"}
    filterset_fields = ["kind", "is_archived"]
    ordering_fields = ["name", "debt", "overdue_debt", "created_at"]

    def get_queryset(self):
        qs = services.with_debt(super().get_queryset())
        params = self.request.query_params
        if params.get("search"):
            term = params["search"].strip()
            digits = "".join(ch for ch in term if ch.isdigit())
            cond = Q(name__icontains=term)
            if digits:
                cond |= Q(phone__contains=digits)
            qs = qs.filter(cond)
        if params.get("has_debt") == "true":
            qs = qs.filter(debt__gt=0)
        if params.get("overdue") == "true":
            qs = qs.filter(overdue_debt__gt=0)
        return qs

    @extend_schema(responses=ReceivableSerializer(many=True))
    @action(detail=True, methods=["get"])
    def receivables(self, request, pk=None):
        customer = self.get_object()
        qs = customer.receivables.select_related("sale")
        if request.query_params.get("open") == "true":
            qs = qs.filter(status=Receivable.OPEN)
        return Response(ReceivableSerializer(qs, many=True).data)

    @extend_schema(request=CustomerPaymentSerializer, responses=CustomerPaymentSerializer)
    @action(detail=True, methods=["get", "post"])
    def payments(self, request, pk=None):
        customer = self.get_object()
        if request.method == "GET":
            page = self.paginate_queryset(customer.payments.select_related("created_by"))
            return self.get_paginated_response(CustomerPaymentSerializer(page, many=True).data)
        if not request.user.has_perm_code("debts.collect"):
            raise DomainError("To'lov qabul qilishga ruxsat yo'q", code="permission_denied",
                              status_code=403)  # fmt: skip
        serializer = CustomerPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        receivable = None
        if data.get("receivable"):
            receivable = Receivable.objects.filter(pk=data["receivable"], customer=customer).first()
            if receivable is None:
                raise DomainError("Nasiya topilmadi", code="not_found", status_code=404)
        payment = services.receive_payment(
            tenant=self.tenant, user=request.user, customer=customer, amount=data["amount"],
            method=data.get("method", "cash"), note=data.get("note", ""), receivable=receivable,
            request=request,
        )  # fmt: skip
        return Response(CustomerPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


def _date_filters(qs, params, field="date"):
    if params.get("date_from"):
        qs = qs.filter(**{f"{field}__gte": params["date_from"]})
    if params.get("date_to"):
        qs = qs.filter(**{f"{field}__lte": params["date_to"]})
    return qs


class SaleViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Savdolar: kassa (POST), tarix (GET), bekor qilish, yig'indi va kassa katalogi."""

    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    read_perm = "sales.create"
    write_perm = "sales.create"
    action_perms = {"cancel": "sales.refund", "summary": "sales.create",
                    "pos_catalog": "sales.create"}  # fmt: skip
    filterset_fields = ["status", "customer", "cashier", "warehouse"]
    ordering_fields = ["created_at", "total", "number"]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return qs
        params = self.request.query_params
        qs = _date_filters(qs, params)
        if params.get("method"):
            qs = qs.filter(payments__method=params["method"]).distinct()
        if params.get("search"):
            term = params["search"].strip()
            qs = (
                qs.filter(number=int(term))
                if term.isdigit()
                else qs.filter(customer__name__icontains=term)
            )
        return services.sales_for_user(qs, self.request.user)

    def _detailed(self, qs):
        return qs.select_related("customer", "cashier", "warehouse").prefetch_related(
            Prefetch("lines", queryset=SaleLine.objects.select_related("product", "unit")),
            "payments",
        )

    def list(self, request, *args, **kwargs):
        qs = self._detailed(self.filter_queryset(self.get_queryset()))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        sale = self._detailed(self.get_queryset()).get(pk=self.get_object().pk)
        return Response(self.get_serializer(sale).data)

    @extend_schema(request=SaleCreateSerializer, responses=SaleSerializer)
    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        items = [
            services.SaleItem(
                product=i["product"], unit=i.get("unit") or i["product"].base_unit,
                qty=i["qty"], price=i.get("price"),
            )
            for i in data["items"]
        ]  # fmt: skip
        sale = services.create_sale(
            tenant=self.tenant, user=request.user, warehouse=data["warehouse"], items=items,
            payments=[services.PaymentIn(p["method"], p["amount"]) for p in data["payments"]],
            customer=data.get("customer"), client_uuid=data.get("client_uuid"),
            due_date=data.get("due_date"), note=data.get("note", ""), request=request,
        )  # fmt: skip
        sale = self._detailed(Sale.objects.filter(pk=sale.pk)).get()
        return Response(self.get_serializer(sale).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=CancelSerializer, responses=SaleSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = services.cancel_sale(
            tenant=self.tenant, user=request.user, sale=self.get_object(),
            reason=serializer.validated_data.get("reason", ""), request=request,
        )  # fmt: skip
        return Response(
            self.get_serializer(self._detailed(Sale.objects.filter(pk=sale.pk)).get()).data
        )

    @extend_schema(
        parameters=[OpenApiParameter("date_from", str), OpenApiParameter("date_to", str)],
        responses=SalesSummarySerializer,
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset()).filter(status=Sale.POSTED)
        agg = qs.aggregate(
            count=Count("id"), total=Sum("total"), discount=Sum("discount_total"),
            cost=Sum("cost_total"),
        )  # fmt: skip
        by_method = dict(
            SalePayment.objects.filter(sale__in=qs.values("pk"))
            .values_list("method").annotate(s=Sum("amount")).values_list("method", "s")
        )  # fmt: skip
        total = agg["total"] or ZERO
        profit = total - (agg["cost"] or ZERO) if request.user.has_perm_code("cost.view") else None
        return Response(SalesSummarySerializer({
            "count": agg["count"], "total": total, "discount": agg["discount"] or ZERO,
            "profit": profit, "by_method": by_method,
        }).data)  # fmt: skip

    @extend_schema(
        parameters=[
            OpenApiParameter("warehouse", int, required=True),
            OpenApiParameter("search", str),
            OpenApiParameter("customer", int),
        ],
        responses=PosProductSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="pos-catalog")
    def pos_catalog(self, request):
        """Kassa uchun: mahsulot + qoldiq + so'mdagi narx (barcha birliklarda)."""
        params = request.query_params
        warehouse = Warehouse.objects.filter(tenant=self.tenant, pk=params.get("warehouse")).first()
        if warehouse is None or not request.user.can_access_branch(warehouse.branch_id):
            raise DomainError("Ombor topilmadi", code="warehouse_not_found", status_code=404)
        customer = Customer.objects.filter(
            tenant=self.tenant, pk=params.get("customer") or 0
        ).first()

        products_qs = ProductFilter(
            data={"search": params.get("search", ""), "is_archived": "false",
                  "category": params.get("category")},
            queryset=Product.objects.filter(tenant=self.tenant).select_related("base_unit", "category"),
            request=request,
        ).qs.prefetch_related(
            Prefetch("units", queryset=ProductUnit.objects.select_related("unit")), "barcodes"
        )[: int(params.get("limit", 60))]  # fmt: skip
        products = list(products_qs)

        fallback = services.default_price_type(self.tenant)
        price_type = (customer.price_type if customer and customer.price_type else None) or fallback
        prices = services.base_prices(products, price_type, fallback)
        rate = None
        if any(p.price_currency == USD for p in products):
            try:
                rate = get_rate(self.tenant, USD).rate
            except RateNotFound:
                rate = None
        stock = dict(
            StockBalance.objects.filter(warehouse=warehouse, product__in=products)
            .values_list("product_id", "qty")
        )  # fmt: skip

        result = []
        for p in products:
            if p.pk not in prices or (p.price_currency == USD and rate is None):
                continue  # narxsiz tovar kassada ko'rinmaydi
            codes: dict[int | None, list[str]] = {}
            for b in p.barcodes.all():
                codes.setdefault(b.product_unit_id, []).append(b.code)
            units = [{"unit": p.base_unit_id, "unit_short": p.base_unit.short, "factor": Decimal(1),
                      "price": services.to_uzs_per_unit(prices[p.pk], p, Decimal(1), rate),
                      "barcodes": codes.get(None, [])}]  # fmt: skip
            units += [
                {"unit": pu.unit_id, "unit_short": pu.unit.short, "factor": pu.factor,
                 "price": services.to_uzs_per_unit(prices[p.pk], p, pu.factor, rate),
                 "barcodes": codes.get(pu.pk, [])}
                for pu in p.units.all()
            ]  # fmt: skip
            result.append({
                "id": p.pk, "name": p.name, "sku": p.sku,
                "barcodes": [b.code for b in p.barcodes.all()],
                "category": p.category.name if p.category else None,
                "allow_fraction": p.base_unit.allow_fraction,
                "stock": stock.get(p.pk, ZERO), "units": units,
            })  # fmt: skip
        return Response(PosProductSerializer(result, many=True).data)
