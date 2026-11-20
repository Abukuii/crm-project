from django.core.management.base import BaseCommand

from apps.currency.services import fetch_cbu_rates


class Command(BaseCommand):
    help = "Markaziy bankdan (CBU) joriy valyuta kurslarini oladi"

    def handle(self, *args, **options):
        count = fetch_cbu_rates()
        self.stdout.write(self.style.SUCCESS(f"{count} ta kurs saqlandi"))
