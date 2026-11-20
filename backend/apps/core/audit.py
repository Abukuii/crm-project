import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from .models import AuditLog


def _jsonable(data: Any) -> Any:
    if data is None:
        return None
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record(
    *,
    action: str,
    entity: str,
    entity_id: Any = "",
    tenant=None,
    user=None,
    before: Any = None,
    after: Any = None,
    request=None,
) -> AuditLog:
    if request is not None and user is None and request.user.is_authenticated:
        user = request.user
    if tenant is None and user is not None:
        tenant = getattr(user, "tenant", None)
    return AuditLog.objects.create(
        tenant=tenant,
        user=user,
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        before=_jsonable(before),
        after=_jsonable(after),
        ip=client_ip(request),
    )
