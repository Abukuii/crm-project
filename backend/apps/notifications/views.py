from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import DomainError
from apps.core.permissions import IsTenantMember

from .models import PushSubscription
from .push import is_enabled, send_to_users


class _Base(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]


class PushKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField(max_length=255)
    auth = serializers.CharField(max_length=255)


class SubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=512)
    keys = PushKeysSerializer()


class UnsubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=512)


ConfigSerializer = inline_serializer(
    "PushConfig",
    {
        "enabled": serializers.BooleanField(),
        "public_key": serializers.CharField(allow_null=True),
        "devices": serializers.IntegerField(),
    },
)


@extend_schema(responses=ConfigSerializer)
class ConfigView(_Base):
    """Push yoqilganmi va brauzer obuna bo'lishi uchun kerakli ochiq kalit."""

    def get(self, request):
        return Response({
            "enabled": is_enabled(),
            "public_key": settings.VAPID_PUBLIC_KEY or None,
            "devices": PushSubscription.objects.filter(user=request.user).count(),
        })  # fmt: skip


@extend_schema(request=SubscribeSerializer, responses=ConfigSerializer)
class SubscribeView(_Base):
    def post(self, request):
        if not is_enabled():
            raise DomainError("Bildirishnomalar sozlanmagan", code="push_disabled")
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Obuna shu brauzerga bog'langan: boshqa xodim kirsa, u o'ziga o'tadi
        PushSubscription.objects.update_or_create(
            endpoint=data["endpoint"],
            defaults={
                "tenant": request.user.tenant,
                "user": request.user,
                "p256dh": data["keys"]["p256dh"],
                "auth": data["keys"]["auth"],
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
            },
        )
        return Response(
            {
                "enabled": True,
                "public_key": settings.VAPID_PUBLIC_KEY,
                "devices": PushSubscription.objects.filter(user=request.user).count(),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(request=UnsubscribeSerializer, responses={204: None})
class UnsubscribeView(_Base):
    def post(self, request):
        serializer = UnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PushSubscription.objects.filter(
            endpoint=serializer.validated_data["endpoint"], user=request.user
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=None,
    responses=inline_serializer("PushTestResult", {"sent": serializers.IntegerField()}),
)
class TestView(_Base):
    """O'ziga sinov bildirishnomasi yuboradi."""

    def post(self, request):
        if not is_enabled():
            raise DomainError("Bildirishnomalar sozlanmagan", code="push_disabled")
        sent = send_to_users(
            [request.user.pk],
            title="Savdo",
            body="Bildirishnomalar ishlayapti ✅",
            url="/",
            tag="test",
        )
        if not sent:
            raise DomainError(
                "Bu qurilma obuna bo'lmagan — avval bildirishnomalarni yoqing",
                code="no_subscription",
            )
        return Response({"sent": sent})
