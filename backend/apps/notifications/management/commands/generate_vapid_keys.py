import base64

from cryptography.hazmat.primitives import serialization
from django.conf import settings
from django.core.management.base import BaseCommand
from py_vapid import Vapid01


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Push bildirishnomalari uchun VAPID kalit juftligini yaratadi"

    def add_arguments(self, parser):
        parser.add_argument("--env", action="store_true",
                            help=".env ga qo'shish uchun tayyor qatorlar chiqaradi")  # fmt: skip
        parser.add_argument("--subject", default="",
                            help="mailto:admin@domen.uz — push xizmatlari bog'lanishi uchun")  # fmt: skip

    def handle(self, *args, **opts):
        if settings.VAPID_PRIVATE_KEY and not opts["env"]:
            self.stdout.write(self.style.WARNING(
                "Diqqat: VAPID kalitlari allaqachon sozlangan. Ularni almashtirsangiz, "
                "mavjud obunalar ishlamay qoladi va xodimlar bildirishnomalarni qayta yoqadi."
            ))  # fmt: skip

        vapid = Vapid01()
        vapid.generate_keys()
        public = _b64(
            vapid.public_key.public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        )
        private = _b64(vapid.private_key.private_numbers().private_value.to_bytes(32, "big"))
        subject = opts["subject"] or settings.VAPID_SUBJECT

        if opts["env"]:
            # setup-server.sh shu chiqishni to'g'ridan-to'g'ri .env ga qo'shadi
            self.stdout.write(f"VAPID_PUBLIC_KEY={public}")
            self.stdout.write(f"VAPID_PRIVATE_KEY={private}")
            self.stdout.write(f"VAPID_SUBJECT={subject}")
            return

        self.stdout.write(self.style.SUCCESS("Quyidagilarni infra/.env ga qo'shing:\n"))
        self.stdout.write(f"VAPID_PUBLIC_KEY={public}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={private}")
        self.stdout.write(f"VAPID_SUBJECT={subject}")
        self.stdout.write("\nSo'ng konteynerlarni qayta ishga tushiring: docker compose up -d")
