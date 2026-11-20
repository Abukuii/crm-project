from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsTenantMember(BasePermission):
    """Faqat faol tenant'ga biriktirilgan faol foydalanuvchi."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        tenant = getattr(user, "tenant", None)
        return tenant is not None and tenant.is_active


class HasPerm(BasePermission):
    """View'dagi ``get_required_perm`` qaytargan ruxsat kodini tekshiradi.

    Yozish amali uchun ruxsat ko'rsatilmagan bo'lsa — rad etiladi (default deny).
    """

    def has_permission(self, request, view) -> bool:
        getter = getattr(view, "get_required_perm", None)
        if getter is None:
            return request.method in SAFE_METHODS
        code = getter(request)
        if code is None:
            return request.method in SAFE_METHODS
        return request.user.has_perm_code(code)
