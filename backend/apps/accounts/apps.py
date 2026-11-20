from django.apps import AppConfig
from django.db.models.signals import post_migrate


def sync_system_roles(sender=None, **kwargs) -> int:
    """Tizim rollari ruxsatlarini koddagi ``DEFAULT_ROLES`` bilan moslaydi.

    Yangi funksiya qo'shilganda mavjud tenantlarning standart rollari ham avtomatik yangilanadi.
    """
    from .models import Role
    from .perms import DEFAULT_ROLES

    updated = 0
    for spec in DEFAULT_ROLES:
        updated += (
            Role.objects.filter(is_system=True, name=spec["name"])
            .exclude(permissions=spec["permissions"])
            .update(permissions=spec["permissions"])
        )
    return updated


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Foydalanuvchilar"

    def ready(self):
        post_migrate.connect(sync_system_roles, sender=self)
