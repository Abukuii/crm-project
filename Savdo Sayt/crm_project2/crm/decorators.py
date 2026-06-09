from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps


def admin_required(view_func):
    """Faqat Admin guruh yoki superuser kirishi mumkin."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(name='Admin').exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapper


def menejer_yoki_admin(view_func):
    """Admin yoki Menejer kirishi mumkin."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Menejer']).exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapper


def is_admin(user):
    """Template va view larda tekshirish uchun yordamchi."""
    return user.is_superuser or user.groups.filter(name='Admin').exists()


def is_menejer(user):
    return user.groups.filter(name='Menejer').exists()
