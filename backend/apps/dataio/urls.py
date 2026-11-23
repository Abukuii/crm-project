from django.urls import path

from .views import (
    ProductExportView,
    ProductImportView,
    ProductTemplateView,
    SalesExportView,
    StatsExportView,
)

urlpatterns = [
    path("products/template/", ProductTemplateView.as_view(), name="products-template"),
    path("products/import/", ProductImportView.as_view(), name="products-import"),
    path("products/export/", ProductExportView.as_view(), name="products-export"),
    path("sales/export/", SalesExportView.as_view(), name="sales-export"),
    path("stats/export/", StatsExportView.as_view(), name="stats-export"),
]
