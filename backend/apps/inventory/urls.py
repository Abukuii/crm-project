from rest_framework.routers import SimpleRouter

from .views import StockBalanceViewSet, StockMoveViewSet, WarehouseViewSet

router = SimpleRouter()
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("balances", StockBalanceViewSet, basename="balance")
router.register("moves", StockMoveViewSet, basename="move")

urlpatterns = router.urls
