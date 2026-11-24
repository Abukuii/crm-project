from django.urls import path

from .views import ConfigView, SubscribeView, TestView, UnsubscribeView

urlpatterns = [
    path("push/config/", ConfigView.as_view(), name="push-config"),
    path("push/subscribe/", SubscribeView.as_view(), name="push-subscribe"),
    path("push/unsubscribe/", UnsubscribeView.as_view(), name="push-unsubscribe"),
    path("push/test/", TestView.as_view(), name="push-test"),
]
