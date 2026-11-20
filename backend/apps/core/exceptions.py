"""Yagona xato formati: {"error": {"code", "message", "details"}}."""

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(exceptions.APIException):
    """Biznes qoidasi buzilganda (qoldiq yetmaydi, limit oshdi va h.k.)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "domain_error"
    default_detail = "Amalni bajarib bo'lmadi"

    def __init__(self, message=None, *, code=None, details=None, status_code=None):
        self.message = message or self.default_detail
        self.code = code or self.default_code
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=self.message, code=self.code)


class InsufficientStock(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "insufficient_stock"
    default_detail = "Qoldiq yetarli emas"


_MESSAGES = {
    "not_authenticated": "Tizimga kirish talab qilinadi",
    "authentication_failed": "Login yoki parol noto'g'ri",
    "permission_denied": "Bu amal uchun ruxsat yo'q",
    "not_found": "Topilmadi",
    "throttled": "Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring",
    "method_not_allowed": "Bu usul qo'llab-quvvatlanmaydi",
}


def _payload(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details}}


def api_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        return Response(
            _payload("protected", "Bu yozuv boshqa ma'lumotlarda ishlatilgan, o'chirib bo'lmaydi"),
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(
            exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        )
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    if isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, DomainError):
        response.data = _payload(exc.code, exc.message, exc.details)
    elif isinstance(exc, exceptions.ValidationError):
        response.data = _payload("validation_error", "Ma'lumotlar noto'g'ri", response.data)
    else:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        code = codes if isinstance(codes, str) else getattr(exc, "default_code", "error")
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        message = _MESSAGES.get(code) or (str(detail) if detail else "Xatolik")
        response.data = _payload(code, message)
    return response
