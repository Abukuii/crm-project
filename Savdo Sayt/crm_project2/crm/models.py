from django.db import models
from django.db.models import F
from django.utils import timezone


class DollarKurs(models.Model):
    """Dollar kursini global saqlash uchun. Faqat bitta yozuv bo'ladi (pk=1)."""
    kurs = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Dollar kursi (so'm)")
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dollar kursi"
        verbose_name_plural = "Dollar kursi"

    def __str__(self):
        return f"1 USD = {self.kurs} so'm"

    @classmethod
    def olish(cls):
        """Joriy kursni qaytaradi, topilmasa None."""
        obj = cls.objects.first()
        return float(obj.kurs) if obj else None

    @classmethod
    def saqlash(cls, kurs):
        """Kursni yangilaydi yoki yaratadi (singleton)."""
        obj, _ = cls.objects.update_or_create(
            pk=1,
            defaults={'kurs': kurs}
        )
        return obj


class Mahsulot(models.Model):
    nomi = models.CharField(max_length=200, verbose_name="Mahsulot nomi")
    qoldi = models.IntegerField(default=0, verbose_name="Qoldi (joriy)")
    narxi = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Narxi (so'm)")
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)
    valyuta = models.CharField(
        max_length=3,
        choices=[('uzs', "So'm"), ('usd', 'Dollar')],
        default='uzs',
        verbose_name="Narx valyutasi"
    )

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        ordering = ['-yaratilgan']

    def __str__(self):
        return self.nomi

    @property
    def jami_kirim(self):
        # Annotate bilan ishlatilmasa fallback sifatida
        if hasattr(self, '_jami_kirim'):
            return self._jami_kirim
        from django.db.models import Sum
        result = self.kirimlar.aggregate(s=Sum('soni'))['s']
        return result or 0

    @property
    def jami_sotildi(self):
        from django.db.models import Sum
        result = SavdoItem.objects.filter(mahsulot=self).aggregate(s=Sum('soni'))['s']
        return result or 0

    @property
    def kam_qolgan(self):
        return self.qoldi <= 10


def _get_dollar_kursi():
    """Avval DB dan, topilmasa CBU dan kursni oladi."""
    kurs = DollarKurs.olish()
    if kurs:
        return kurs
    try:
        import requests
        import xml.etree.ElementTree as ET
        from datetime import date
        bugun = date.today().strftime('%d.%m.%Y')
        url = f"https://cbu.uz/uz/arkhiv-kursov-valyut/xml/R01235/{bugun}/"
        resp = requests.get(url, timeout=5)
        root = ET.fromstring(resp.content)
        for item in root.findall('Currency'):
            code = item.find('Ccy')
            rate = item.find('Rate')
            if code is not None and code.text == 'USD' and rate is not None:
                return float(rate.text.replace(',', '.'))
    except Exception:
        pass
    return None


class Kirim(models.Model):
    VALYUTA_TURI = [
        ('uzs', "So'm"),
        ('usd', 'Dollar'),
    ]
    NARX_TURI = [
        ('aniq', "Aniq narx"),
        ('foizli', "Foiz qo'shib"),
    ]

    mahsulot = models.ForeignKey(
        Mahsulot, on_delete=models.CASCADE,
        related_name='kirimlar', verbose_name="Mahsulot"
    )
    soni = models.IntegerField(verbose_name="Kirim soni")
    narxi = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="Kirim narxi (so'm)")
    valyuta = models.CharField(max_length=3, choices=VALYUTA_TURI, default='uzs', verbose_name="Valyuta")
    asl_narx = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Sotib olish narxi")
    foiz = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Ustama foizi (%)")
    narx_turi = models.CharField(max_length=10, choices=NARX_TURI, default='aniq', verbose_name="Narx turi")
    dollar_kursi = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Dollar kursi")
    izoh = models.CharField(max_length=300, blank=True, verbose_name="Izoh")
    sana = models.DateField(default=timezone.now, verbose_name="Sana")
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kirim"
        verbose_name_plural = "Kirimlar"
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.mahsulot.nomi} — +{self.soni} ta ({self.sana})"

    def hisobla_sotish_narxi(self):
        """Sotib olish narxi asosida so'mda sotish narxini hisoblaydi."""
        if not self.asl_narx:
            return None

        narx = float(self.asl_narx)

        if self.valyuta == 'usd':
            kurs = float(self.dollar_kursi) if self.dollar_kursi else _get_dollar_kursi()
            if not kurs:
                return None
            narx = narx * kurs

        if self.narx_turi == 'foizli' and self.foiz:
            narx = narx * (1 + float(self.foiz) / 100)

        return int(narx)

    def save(self, *args, **kwargs):
        sotish_narxi = self.hisobla_sotish_narxi()
        if sotish_narxi:
            self.narxi = sotish_narxi

        if not self.pk:
            super().save(*args, **kwargs)
            # F() bilan race condition xavfsiz yangilash
            Mahsulot.objects.filter(pk=self.mahsulot_id).update(qoldi=F('qoldi') + self.soni)
            if sotish_narxi:
                Mahsulot.objects.filter(pk=self.mahsulot_id).update(narxi=sotish_narxi)
        else:
            old = Kirim.objects.get(pk=self.pk)
            farq = self.soni - old.soni
            super().save(*args, **kwargs)
            if farq != 0:
                Mahsulot.objects.filter(pk=self.mahsulot_id).update(qoldi=F('qoldi') + farq)
            if sotish_narxi:
                Mahsulot.objects.filter(pk=self.mahsulot_id).update(narxi=sotish_narxi)

    def delete(self, *args, **kwargs):
        mahsulot_id = self.mahsulot_id
        soni = self.soni
        super().delete(*args, **kwargs)
        # Manfiy bo'lib ketmasligi uchun GREATEST(qoldi - soni, 0)
        from django.db.models.functions import Greatest
        Mahsulot.objects.filter(pk=mahsulot_id).update(
            qoldi=Greatest(F('qoldi') - soni, 0)
        )


class Mijoz(models.Model):
    ism_familiya = models.CharField(max_length=200, verbose_name="Ism Familiya")
    telefon = models.CharField(max_length=20, verbose_name="Telefon raqami")
    manzil = models.CharField(max_length=300, blank=True, verbose_name="Manzil")
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mijoz"
        verbose_name_plural = "Mijozlar"
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.ism_familiya} - {self.telefon}"

    @property
    def jami_qarz(self):
        # Barcha to'lovlar chiqarilib, haqiqiy qolgan qarz
        return sum(s.qolgan_qarz for s in self.savdolar.filter(to_langan=False))


class Savdo(models.Model):
    TOLOV_TURI = [
        ('naqd', 'Naqd pul'),
        ('nasiya', 'Nasiya'),
        ('plastik', 'Plastik karta'),
    ]

    mijoz = models.ForeignKey(Mijoz, on_delete=models.CASCADE, related_name='savdolar', null=True, blank=True, verbose_name="Mijoz")
    sana = models.DateField(default=timezone.now, verbose_name="Sana")
    tolov_turi = models.CharField(max_length=10, choices=TOLOV_TURI, default='naqd', verbose_name="To'lov turi")
    jami_summa = models.DecimalField(max_digits=14, decimal_places=0, default=0, verbose_name="Jami summa")
    bosh_tolov = models.DecimalField(max_digits=14, decimal_places=0, default=0, verbose_name="Boshlang'ich to'lov")
    to_langan = models.BooleanField(default=True, verbose_name="To'langan")
    izoh = models.TextField(blank=True, verbose_name="Izoh")
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Savdo"
        verbose_name_plural = "Savdolar"
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"Savdo #{self.pk} - {self.sana}"

    @property
    def tolov_tarixi_jami(self):
        """Keyingi to'lovlar jami (bosh_tolov hisobga olinmaydi)"""
        return self.tolov_tarixlari.aggregate(s=models.Sum('summa'))['s'] or 0

    @property
    def toʻlangan_jami(self):
        """Barcha to'lovlar: bosh_tolov + keyingi to'lovlar"""
        return int(self.bosh_tolov) + int(self.tolov_tarixi_jami)

    @property
    def qolgan_qarz(self):
        """Hozirgi qarz: jami_summa - barcha to'lovlar"""
        return int(self.jami_summa) - self.toʻlangan_jami

    def save(self, *args, **kwargs):
        if self.pk:
            self.jami_summa = sum(item.jami for item in self.savdo_itemlar.all())
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Itemlarni oldin yig'ib olamiz
        itemlar = list(
            self.savdo_itemlar.select_related('mahsulot').values('mahsulot_id', 'soni')
        )
        super().delete(*args, **kwargs)
        # F() bilan har bir mahsulot qoldig'ini tiklash
        for item in itemlar:
            Mahsulot.objects.filter(pk=item['mahsulot_id']).update(
                qoldi=F('qoldi') + item['soni']
            )


class SavdoItem(models.Model):
    savdo = models.ForeignKey(Savdo, on_delete=models.CASCADE, related_name='savdo_itemlar')
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, verbose_name="Mahsulot")
    soni = models.IntegerField(default=1, verbose_name="Soni")
    narxi = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Narxi (asl)")
    kelishilgan_narx = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="Kelishilgan narx")

    class Meta:
        verbose_name = "Savdo element"
        verbose_name_plural = "Savdo elementlar"

    def __str__(self):
        return f"{self.mahsulot.nomi} x {self.soni}"

    @property
    def joriy_narx(self):
        return self.kelishilgan_narx if self.kelishilgan_narx else self.narxi

    @property
    def jami(self):
        return self.joriy_narx * self.soni

    @property
    def chegirma(self):
        if self.kelishilgan_narx and self.kelishilgan_narx < self.narxi:
            return (self.narxi - self.kelishilgan_narx) * self.soni
        return 0


class TolovTarixi(models.Model):
    """Nasiya savdolar uchun qisman to'lov tarixi"""
    savdo = models.ForeignKey(
        Savdo, on_delete=models.CASCADE,
        related_name='tolov_tarixlari', verbose_name="Savdo"
    )
    summa = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="To'lov summasi")
    sana = models.DateField(default=timezone.now, verbose_name="Sana")
    izoh = models.CharField(max_length=300, blank=True, verbose_name="Izoh")
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "To'lov tarixi"
        verbose_name_plural = "To'lov tarixi"
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"Savdo #{self.savdo_id} — {self.summa} so'm ({self.sana})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Qarz to'liq to'langan bo'lsa, savdoni to'langan deb belgilash
        savdo = self.savdo
        if savdo.qolgan_qarz <= 0:
            Savdo.objects.filter(pk=savdo.pk).update(to_langan=True)

    def delete(self, *args, **kwargs):
        savdo = self.savdo
        super().delete(*args, **kwargs)
        # O'chirilganda qarz qaytishi mumkin, to_langan ni qayta hisoblash
        savdo.refresh_from_db()
        if savdo.qolgan_qarz > 0:
            Savdo.objects.filter(pk=savdo.pk).update(to_langan=False)


class Xarajat(models.Model):
    KATEGORIYA = [
        ('ijara', 'Ijara'),
        ('transport', 'Transport'),
        ('maosh', 'Maosh'),
        ('kommunal', 'Kommunal'),
        ('boshqa', 'Boshqa'),
    ]
    nomi = models.CharField(max_length=200, verbose_name="Xarajat nomi")
    summa = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="Summa (so'm)")
    kategoriya = models.CharField(max_length=20, choices=KATEGORIYA, default='boshqa', verbose_name="Kategoriya")
    sana = models.DateField(default=timezone.now, verbose_name="Sana")
    izoh = models.TextField(blank=True, verbose_name="Izoh")
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xarajat"
        verbose_name_plural = "Xarajatlar"
        ordering = ['-sana', '-yaratilgan']

    def __str__(self):
        return f"{self.nomi} — {self.summa} so'm"


class Eslatma(models.Model):
    DARAJA = [
        ('oddiy', 'Oddiy'),
        ('muhim', 'Muhim'),
        ('shoshilinch', 'Shoshilinch'),
    ]
    matn = models.TextField(verbose_name="Eslatma matni")
    daraja = models.CharField(max_length=15, choices=DARAJA, default='oddiy', verbose_name="Muhimlik darajasi")
    bajarildi = models.BooleanField(default=False, verbose_name="Bajarildi")
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Eslatma"
        verbose_name_plural = "Eslatmalar"
        ordering = ['bajarildi', '-yaratilgan']

    def __str__(self):
        return self.matn[:50]


# ─── TUN REJIMI ───────────────────────────────────────────────────────────────
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    tun_rejimi = models.BooleanField(default=False, verbose_name="Tun rejimi")

    class Meta:
        verbose_name = "Foydalanuvchi profili"
        verbose_name_plural = "Foydalanuvchi profillari"

    def __str__(self):
        return f"{self.user.username} profili"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Yangi user yaratilganda avtomatik profil ochiladi."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
