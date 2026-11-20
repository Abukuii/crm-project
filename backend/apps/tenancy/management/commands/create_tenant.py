import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.services import provision_tenant


class Command(BaseCommand):
    help = "Yangi biznes (tenant) va uning egasini yaratadi"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Biznes nomi")
        parser.add_argument("--owner", required=True, help="Egasining login nomi")
        parser.add_argument("--password", help="Parol (berilmasa so'raladi)")
        parser.add_argument("--phone", default="")

    def handle(self, *args, **opts):
        from apps.accounts.models import User

        if User.objects.filter(username=opts["owner"]).exists():
            raise CommandError(f"'{opts['owner']}' login band")
        password = opts["password"] or getpass.getpass("Parol: ")
        if len(password) < 8:
            raise CommandError("Parol kamida 8 belgi bo'lishi kerak")
        result = provision_tenant(
            name=opts["name"],
            owner_username=opts["owner"],
            owner_password=password,
            phone=opts["phone"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant yaratildi: {result.tenant.name} (id={result.tenant.pk}), egasi: {opts['owner']}"
            )
        )
