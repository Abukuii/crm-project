from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.views import TenantScopedMixin

from .models import ExchangeRate
from .serializers import CurrentRateSerializer, ExchangeRateSerializer, ManualRateSerializer
from .services import get_rate, set_manual_rate


class ExchangeRateViewSet(TenantScopedMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Kurslar tarixi (CBU + do'konning o'z kurslari), joriy kurs va qo'lda kiritish."""

    serializer_class = ExchangeRateSerializer
    read_perm = None  # tenant a'zolari ko'ra oladi
    write_perm = "price.edit"
    filterset_fields = ["currency", "source"]

    queryset = ExchangeRate.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ExchangeRate.objects.none()
        return ExchangeRate.objects.filter(
            Q(tenant_id=self.request.user.tenant_id) | Q(tenant__isnull=True)
        )

    @extend_schema(request=ManualRateSerializer, responses=ExchangeRateSerializer)
    def create(self, request):
        serializer = ManualRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = set_manual_rate(
            tenant=self.tenant,
            user=request.user,
            currency=serializer.validated_data["currency"],
            rate=serializer.validated_data["rate"],
            on=serializer.validated_data.get("date"),
            request=request,
        )
        return Response(ExchangeRateSerializer(obj).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter("currency", str, default="USD")],
        responses=CurrentRateSerializer,
    )
    @action(detail=False, methods=["get"])
    def current(self, request):
        info = get_rate(self.tenant, request.query_params.get("currency", "USD"))
        return Response(CurrentRateSerializer(info).data)
