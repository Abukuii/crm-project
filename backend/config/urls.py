from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import HealthView

api_v1 = [
    path("auth/", include("apps.accounts.urls_auth")),
    path("accounts/", include("apps.accounts.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("currency/", include("apps.currency.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("tenancy/", include("apps.tenancy.urls")),
    path("purchasing/", include("apps.purchasing.urls")),
    path("sales/", include("apps.sales.urls")),
    path("finance/", include("apps.finance.urls")),
    path("notes/", include("apps.reminders.views")),
    path("reports/", include("apps.reports.views")),
    path("dataio/", include("apps.dataio.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
