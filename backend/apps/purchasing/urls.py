from rest_framework.routers import SimpleRouter

from .views import PurchaseViewSet, SupplierViewSet

router = SimpleRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("purchases", PurchaseViewSet, basename="purchase")

urlpatterns = router.urls
