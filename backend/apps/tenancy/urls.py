from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import BranchViewSet, CurrentTenantView

router = SimpleRouter()
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = [path("current/", CurrentTenantView.as_view(), name="tenant-current"), *router.urls]
