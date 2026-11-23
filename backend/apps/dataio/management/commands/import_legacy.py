import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.dataio.legacy import LegacyImportError, Source, import_legacy
from apps.tenancy.models import Tenant
from apps.tenancy.services import provision_tenant


class Command(BaseCommand):
    help = "Eski tizim (savdolarim.uz 1.0) bazasidan ma'lumotlarni yangi biznesga ko'chiradi"

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True,
                            help="Eski baza: postgres://user:pass@host:5432/crm_db")  # fmt: skip
        parser.add_argument("--tenant", help="Mavjud biznes slug'i (bo'lmasa --name bilan yangisi)")
        parser.add_argument("--name", help="Yangi biznes nomi")
        parser.add_argument("--owner", help="Yangi biznes egasining logini")
        parser.add_argument("--password", help="Egasining paroli (berilmasa so'raladi)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Tekshirish: hammasi bajariladi, lekin saqlanmaydi")  # fmt: skip

    def handle(self, *args, **opts):
        if opts["tenant"]:
            tenant = Tenant.objects.filter(slug=opts["tenant"]).first()
            if tenant is None:
                raise CommandError(f"'{opts['tenant']}' biznesi topilmadi")
            owner = next((u for u in User.objects.filter(tenant=tenant) if u.is_owner), None)
            if owner is None:
                raise CommandError("Biznesda egasi yo'q")
        else:
            if not (opts["name"] and opts["owner"]):
                raise CommandError("--tenant yoki (--name va --owner) kerak")
            if opts["dry_run"]:
                raise CommandError("--dry-run faqat mavjud biznes bilan (--tenant) ishlaydi")
            if User.objects.filter(username=opts["owner"]).exists():
                raise CommandError(f"'{opts['owner']}' logini band")
            password = opts["password"] or getpass.getpass("Egasining yangi paroli: ")
            if len(password) < 8:
                raise CommandError("Parol kamida 8 belgi")
            result = provision_tenant(name=opts["name"], owner_username=opts["owner"],
                                      owner_password=password)  # fmt: skip
            tenant, owner = result.tenant, result.owner
            self.stdout.write(f"Biznes yaratildi: {tenant.name} (slug: {tenant.slug})")

        source = Source(opts["source"])
        try:
            report = import_legacy(source=source, tenant=tenant, owner=owner,
                                   dry_run=opts["dry_run"])  # fmt: skip
        except LegacyImportError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            source.close()

        title = "TEKSHIRUV (hech narsa saqlanmadi)" if opts["dry_run"] else "KO'CHIRISH TUGADI"
        self.stdout.write(self.style.SUCCESS(f"\n=== {title}: {tenant.name} ==="))
        for key, value in sorted(report.counts.items()):
            self.stdout.write(f"  {key:<24} {value}")
        self.stdout.write("\nSolishtirish (eski -> yangi):")
        stock_ok = report.old_stock_units == report.new_stock_units
        debt_ok = report.old_debt == report.new_debt
        self.stdout.write(f"  Qoldiq (dona)  {report.old_stock_units} -> {report.new_stock_units}"
                          f"  {'OK' if stock_ok else 'FARQ BOR!'}")  # fmt: skip
        self.stdout.write(f"  Ochiq qarz     {report.old_debt} -> {report.new_debt}"
                          f"  {'OK' if debt_ok else 'FARQ BOR!'}")  # fmt: skip
        if report.warnings:
            self.stdout.write(self.style.WARNING(f"\nOgohlantirishlar ({len(report.warnings)}):"))
            for w in report.warnings[:50]:
                self.stdout.write(f"  - {w}")
        if report.counts.get("tannarx_taxminiy"):
            self.stdout.write(self.style.WARNING(
                f"\n{report.counts['tannarx_taxminiy']} ta mahsulotning xarid narxi eski tizimda yo'q edi — "
                "tannarx sifatida sotish narxi olindi. Foyda hisobi to'g'ri bo'lishi uchun ularni "
                "keyingi kirimlarda haqiqiy narx bilan kiriting."
            ))  # fmt: skip
