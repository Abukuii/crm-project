from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasPerm, IsTenantMember

from .services import dashboard

M = {"max_digits": 18, "decimal_places": 2}


class PeriodSerializer(serializers.Serializer):
    sales_count = serializers.IntegerField()
    revenue = serializers.DecimalField(**M)
    discount = serializers.DecimalField(**M)
    avg_check = serializers.DecimalField(**M)
    expenses = serializers.DecimalField(**M)
    returns = serializers.DecimalField(**M)
    gross_profit = serializers.DecimalField(**M, required=False)
    net_profit = serializers.DecimalField(**M, required=False)


class DayRevenueSerializer(serializers.Serializer):
    date = serializers.DateField()
    revenue = serializers.DecimalField(**M)


class TopProductSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    qty = serializers.DecimalField(max_digits=14, decimal_places=3)
    revenue = serializers.DecimalField(**M)


class DebtSerializer(serializers.Serializer):
    total = serializers.DecimalField(**M)
    overdue = serializers.DecimalField(**M)
    debtors = serializers.IntegerField()


class RecentSaleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    number = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    total = serializers.DecimalField(**M)
    customer = serializers.CharField(allow_null=True)


class DashboardSerializer(serializers.Serializer):
    today = PeriodSerializer()
    yesterday = PeriodSerializer()
    month = PeriodSerializer()
    prev_month = PeriodSerializer()
    week = DayRevenueSerializer(many=True)
    today_by_method = serializers.DictField(child=serializers.DecimalField(**M))
    top_products = TopProductSerializer(many=True)
    debt = DebtSerializer()
    low_stock_count = serializers.IntegerField()
    recent_sales = RecentSaleSerializer(many=True)


@extend_schema(responses=DashboardSerializer)
class DashboardView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, HasPerm]

    def get_required_perm(self, request):
        return "reports.view"

    def get(self, request):
        return Response(DashboardSerializer(dashboard(request.user.tenant, request.user)).data)


urlpatterns = [path("dashboard/", DashboardView.as_view(), name="dashboard")]
