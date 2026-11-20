from rest_framework.routers import SimpleRouter

from .views import ExchangeRateViewSet

router = SimpleRouter()
router.register("rates", ExchangeRateViewSet, basename="rate")

urlpatterns = router.urls
