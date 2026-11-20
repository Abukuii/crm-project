from rest_framework.routers import SimpleRouter

from .views import BrandViewSet, CategoryViewSet, PriceTypeViewSet, ProductViewSet, UnitViewSet

router = SimpleRouter()
router.register("units", UnitViewSet, basename="unit")
router.register("categories", CategoryViewSet, basename="category")
router.register("brands", BrandViewSet, basename="brand")
router.register("price-types", PriceTypeViewSet, basename="price-type")
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls
