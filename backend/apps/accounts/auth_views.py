"""Autentifikatsiya: access token javobda, refresh token httpOnly cookie'da."""

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core import audit
from apps.core.exceptions import DomainError
from apps.core.permissions import IsTenantMember

from .models import User
from .serializers import (
    AccessSerializer,
    AuthResponseSerializer,
    LoginRequestSerializer,
    LoginSerializer,
    MeSerializer,
    PinLoginSerializer,
    PinUserSerializer,
)


def _cookie_cfg() -> dict:
    return settings.JWT_REFRESH_COOKIE


def _set_refresh_cookie(response: Response, refresh: str) -> None:
    cfg = _cookie_cfg()
    response.set_cookie(
        cfg["name"],
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=cfg["path"],
        secure=cfg["secure"],
        httponly=True,
        samesite=cfg["samesite"],
    )


def _clear_refresh_cookie(response: Response) -> None:
    cfg = _cookie_cfg()
    response.delete_cookie(cfg["name"], path=cfg["path"], samesite=cfg["samesite"])


def _issue_tokens(user: User) -> tuple[str, str]:
    refresh = LoginSerializer.get_token(user)
    return str(refresh.access_token), str(refresh)


@extend_schema(request=LoginRequestSerializer, responses=AuthResponseSerializer)
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except (serializers.ValidationError, AuthenticationFailed):
            raise DomainError(
                "Login yoki parol noto'g'ri",
                code="invalid_credentials",
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from None
        user = serializer.user
        audit.record(
            action="auth.login", entity="user", entity_id=user.pk, user=user, request=request
        )
        response = Response(
            {"access": serializer.validated_data["access"], "user": MeSerializer(user).data}
        )
        _set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


@extend_schema(request=None, responses=AccessSerializer)
class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.COOKIES.get(_cookie_cfg()["name"])
        if not token:
            raise DomainError(
                "Sessiya topilmadi",
                code="no_refresh_token",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = TokenRefreshSerializer(data={"refresh": token})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken, serializers.ValidationError):
            response = Response(
                {
                    "error": {
                        "code": "session_expired",
                        "message": "Sessiya tugagan",
                        "details": None,
                    }
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(response)
            return response
        response = Response({"access": serializer.validated_data["access"]})
        if "refresh" in serializer.validated_data:
            _set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


@extend_schema(request=None, responses={204: OpenApiResponse(description="Chiqildi")})
class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.COOKIES.get(_cookie_cfg()["name"])
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


@extend_schema(request=MeSerializer, responses=MeSerializer)
class MeView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        allowed = {
            k: v
            for k, v in request.data.items()
            if k in ("first_name", "last_name", "phone", "language", "theme")
        }
        serializer = MeSerializer(request.user, data=allowed, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema(request=PinLoginSerializer, responses=AuthResponseSerializer)
class PinLoginView(APIView):
    """Kassada tez almashish: shu tenant'dagi boshqa xodim PIN bilan kiradi."""

    permission_classes = [IsAuthenticated, IsTenantMember]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "pin"

    def post(self, request):
        serializer = PinLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            pk=serializer.validated_data["user_id"],
            tenant_id=request.user.tenant_id,
            is_active=True,
        ).first()
        if user is None or not user.check_pin(serializer.validated_data["pin"]):
            raise DomainError(
                "PIN noto'g'ri", code="invalid_pin", status_code=status.HTTP_401_UNAUTHORIZED
            )
        access, refresh = _issue_tokens(user)
        audit.record(
            action="auth.pin_login",
            entity="user",
            entity_id=user.pk,
            user=user,
            request=request,
            after={"from_user": request.user.pk},
        )
        response = Response({"access": access, "user": MeSerializer(user).data})
        _set_refresh_cookie(response, refresh)
        return response


@extend_schema(responses=PinUserSerializer(many=True))
class PinUsersView(APIView):
    """PIN o'rnatilgan xodimlar ro'yxati (kassada almashish uchun)."""

    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request):
        users = (
            User.objects.filter(tenant_id=request.user.tenant_id, is_active=True)
            .exclude(pin_hash="")
            .order_by("first_name", "username")
        )
        return Response(
            [
                {"id": u.pk, "username": u.username, "full_name": u.get_full_name() or u.username}
                for u in users
            ]
        )
