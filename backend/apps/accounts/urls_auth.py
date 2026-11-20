from django.urls import path

from .auth_views import LoginView, LogoutView, MeView, PinLoginView, PinUsersView, RefreshView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("pin-login/", PinLoginView.as_view(), name="auth-pin-login"),
    path("pin-users/", PinUsersView.as_view(), name="auth-pin-users"),
]
