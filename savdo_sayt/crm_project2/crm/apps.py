from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm'
    verbose_name = 'CRM Tizimi'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(guruhlar_yaratish, sender=self)

        """Ilova tayyor bo'lganda signallarni ulaydi."""
        try:
            from telegram_bot.signals_for_crm import connect_signals
            connect_signals()
        except ImportError:
            # telegram_bot o'rnatilmagan bo'lsa, o'tkazib yuboradi
            pass


def guruhlar_yaratish(sender, **kwargs):
    """Migrate qilinganda Admin va Menejer guruhlarini avtomatik yaratadi."""
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    # Admin guruhi
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    # Menejer guruhi
    menejer_group, _ = Group.objects.get_or_create(name='Menejer')
