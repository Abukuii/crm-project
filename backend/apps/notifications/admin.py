from django.contrib import admin

from .models import PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "user_agent", "last_sent_at", "created_at")
    list_filter = ("tenant",)
    search_fields = ("endpoint",)
