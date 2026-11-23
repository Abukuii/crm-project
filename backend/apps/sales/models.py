from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TenantModel
from apps.core.money import MoneyField, PriceField, QtyField


class Customer(TenantModel):
    KIND_CHOICES = [("person", "Jismoniy shaxs"), ("master", "Usta / pudratchi"),
                    ("company", "Yuridik shaxs")]  # fmt: skip

    name = models.CharField("F.I.Sh. / nomi", max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="person")
    inn = models.CharField("INN", max_length=20, blank=True)
    price_type = models.ForeignKey(
        "catalog.PriceType", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # None — limit yo'q
    credit_limit = MoneyField(null=True, blank=True, default=None)
    payment_days = models.PositiveIntegerField("Nasiya muddati (kun)", default=0)
    note = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "phone"], condition=~Q(phone=""), name="uniq_customer_phone"
            )
        ]

    def __str__(self) -> str:
        return self.name


class Sale(TenantModel):
    POSTED, CANCELLED = "posted", "cancelled"
    STATUS_CHOICES = [(POSTED, "O'tkazilgan"), (CANCELLED, "Bekor qilingan")]

    number = models.PositiveIntegerField()
    client_uuid = models.UUIDField(null=True, blank=True)  # takroriy yuborishdan himoya
    date = models.DateField(default=timezone.localdate, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=POSTED)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="+")
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, null=True, blank=True, related_name="sales"
    )
    price_type = models.ForeignKey(
        "catalog.PriceType", on_delete=models.PROTECT, null=True, related_name="+"
    )
    rate = PriceField(null=True, blank=True)  # USD kursi (dollar narxli tovar bo'lsa)
    subtotal = MoneyField()  # ro'yxat narxida
    discount_total = MoneyField()
    total = MoneyField()
    cost_total = MoneyField()
    note = models.CharField(max_length=300, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    cancel_reason = models.CharField(max_length=300, blank=True)
    shift = models.ForeignKey(
        "Shift", on_delete=models.PROTECT, null=True, blank=True, related_name="sales"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="uniq_sale_number"),
            models.UniqueConstraint(
                fields=["tenant", "client_uuid"],
                condition=Q(client_uuid__isnull=False),
                name="uniq_sale_client_uuid",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "date", "status"])]

    def __str__(self) -> str:
        return f"Savdo #{self.number}"


class SaleLine(TenantModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    unit = models.ForeignKey("catalog.Unit", on_delete=models.PROTECT, related_name="+")
    factor = QtyField()
    qty = QtyField()
    base_qty = QtyField()
    list_price = MoneyField()  # 1 birlik ro'yxat narxi (so'm)
    price = MoneyField()  # 1 birlik sotilgan (kelishilgan) narx
    discount = MoneyField()
    total = MoneyField()
    unit_cost = PriceField(null=True)  # asosiy birlik tannarxi (sotilgan paytdagi)
    cost_total = MoneyField()
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class SalePayment(TenantModel):
    CASH, CARD, TRANSFER, CREDIT = "cash", "card", "transfer", "credit"
    METHOD_CHOICES = [(CASH, "Naqd"), (CARD, "Plastik karta"), (TRANSFER, "O'tkazma"),
                      (CREDIT, "Nasiya")]  # fmt: skip

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    amount = MoneyField()


class Receivable(TenantModel):
    """Nasiya: bitta savdoning to'lanmagan qismi."""

    OPEN, CLOSED, CANCELLED = "open", "closed", "cancelled"
    STATUS_CHOICES = [(OPEN, "Ochiq"), (CLOSED, "Yopilgan"), (CANCELLED, "Bekor qilingan")]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="receivables")
    sale = models.OneToOneField(Sale, on_delete=models.PROTECT, related_name="receivable")
    amount = MoneyField()
    paid = MoneyField()
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN, db_index=True)

    class Meta:
        ordering = ["due_date", "id"]

    @property
    def remaining(self):
        return self.amount - self.paid


class CustomerPayment(TenantModel):
    """Mijozdan nasiya bo'yicha olingan to'lov (eski savdolar bo'yicha FIFO taqsimlanadi)."""

    METHOD_CHOICES = [("cash", "Naqd"), ("card", "Plastik karta"), ("transfer", "O'tkazma")]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="payments")
    amount = MoneyField()
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="cash")
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=300, blank=True)
    shift = models.ForeignKey(
        "Shift", on_delete=models.PROTECT, null=True, blank=True, related_name="debt_payments"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]


class PaymentAllocation(TenantModel):
    payment = models.ForeignKey(
        CustomerPayment, on_delete=models.CASCADE, related_name="allocations"
    )
    receivable = models.ForeignKey(Receivable, on_delete=models.PROTECT, related_name="allocations")
    amount = MoneyField()


class Shift(TenantModel):
    """Kassa smenasi: ochilishdagi naqd → savdolar/to'lovlar/qaytarishlar → yopilishda sanalgan naqd."""

    OPEN, CLOSED = "open", "closed"
    STATUS_CHOICES = [(OPEN, "Ochiq"), (CLOSED, "Yopilgan")]

    number = models.PositiveIntegerField()
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="+")
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shifts"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN, db_index=True)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    opening_cash = MoneyField()
    expected_cash = MoneyField(null=True, blank=True, default=None)  # yopilganda hisoblanadi
    counted_cash = MoneyField(null=True, blank=True, default=None)  # kassir sanagan
    difference = MoneyField(null=True, blank=True, default=None)  # sanalgan − kutilgan
    report = models.JSONField(null=True, blank=True)  # Z-hisobot (yopilgandagi holat)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="uniq_shift_number"),
            # Bir kassirda bir vaqtda faqat bitta ochiq smena
            models.UniqueConstraint(
                fields=["cashier"], condition=Q(status="open"), name="uniq_open_shift_per_cashier"
            ),
        ]

    def __str__(self) -> str:
        return f"Smena #{self.number}"


class CashMovement(TenantModel):
    """Smena davomida kassaga naqd kiritish (+) yoki chiqarish (−): inkassatsiya, mayda xarajat."""

    IN, OUT = "in", "out"
    KIND_CHOICES = [(IN, "Kirim"), (OUT, "Chiqim")]

    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name="cash_movements")
    kind = models.CharField(max_length=3, choices=KIND_CHOICES)
    amount = MoneyField()
    note = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["created_at"]


class SaleReturn(TenantModel):
    """Qaytarish (to'liq yoki qisman). Tovar omborga sotilgan tannarxida qaytadi."""

    CASH, CARD, TRANSFER, DEBT = "cash", "card", "transfer", "debt"
    REFUND_CHOICES = [(CASH, "Naqd"), (CARD, "Plastik karta"), (TRANSFER, "O'tkazma"),
                      (DEBT, "Qarzdan ayirish")]  # fmt: skip

    number = models.PositiveIntegerField()
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="returns")
    shift = models.ForeignKey(
        Shift, on_delete=models.PROTECT, null=True, blank=True, related_name="returns"
    )
    date = models.DateField(default=timezone.localdate, db_index=True)
    refund_method = models.CharField(max_length=10, choices=REFUND_CHOICES)
    total = MoneyField()
    cost_total = MoneyField()
    reason = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="uniq_return_number")
        ]


class SaleReturnLine(TenantModel):
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name="lines")
    sale_line = models.ForeignKey(SaleLine, on_delete=models.PROTECT, related_name="returned")
    qty = QtyField()  # savdo qatori birligida
    base_qty = QtyField()
    amount = MoneyField()
    unit_cost = PriceField()
    cost_total = MoneyField()
