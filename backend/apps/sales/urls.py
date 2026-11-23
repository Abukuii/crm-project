from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet, SaleViewSet, ShiftViewSet

router = SimpleRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("sales", SaleViewSet, basename="sale")
router.register("shifts", ShiftViewSet, basename="shift")

urlpatterns = router.urls
