from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import PermissionListView, RoleViewSet, UserViewSet

router = SimpleRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")

urlpatterns = [path("permissions/", PermissionListView.as_view(), name="permissions"), *router.urls]
