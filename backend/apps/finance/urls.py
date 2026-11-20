from rest_framework.routers import SimpleRouter

from .views import ExpenseCategoryViewSet, ExpenseViewSet

router = SimpleRouter()
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("expenses", ExpenseViewSet, basename="expense")

urlpatterns = router.urls
