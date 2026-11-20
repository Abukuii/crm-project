from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet, SaleViewSet

router = SimpleRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("sales", SaleViewSet, basename="sale")

urlpatterns = router.urls
