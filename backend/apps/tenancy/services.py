"""Yangi biznesni (tenant) noldan tayyorlash: filial, ombor, rollar, birliklar, narx turlari, egasi."""

from dataclasses import dataclass

from django.db import transaction
from django.utils.text import slugify

from apps.core import audit

from .models import Branch, Tenant

DEFAULT_UNITS = [
    # (nomi, qisqa, kasr miqdorga ruxsat)
    ("dona", "dona", False),
    ("kilogramm", "kg", True),
    ("tonna", "t", True),
    ("metr", "m", True),
    ("kvadrat metr", "m²", True),
    ("kub metr", "m³", True),
    ("litr", "l", True),
    ("qop", "qop", False),
    ("pachka", "pachka", False),
    ("quti", "quti", False),
    ("rulon", "rulon", False),
    ("list", "list", False),
]

DEFAULT_PRICE_TYPES = [("Chakana", True), ("Ulgurji", False), ("Usta", False)]


@dataclass
class ProvisionResult:
    tenant: Tenant
    branch: Branch
    owner: object


def _unique_slug(name: str) -> str:
    base = slugify(name) or "tenant"
    slug, i = base, 1
    while Tenant.objects.filter(slug=slug).exists():
        i += 1
        slug = f"{base}-{i}"
    return slug


@transaction.atomic
def provision_tenant(
    *,
    name: str,
    owner_username: str,
    owner_password: str,
    owner_first_name: str = "",
    phone: str = "",
) -> ProvisionResult:
    from apps.accounts.models import Role, User
    from apps.accounts.perms import DEFAULT_ROLES
    from apps.catalog.models import PriceType, Unit
    from apps.finance.models import DEFAULT_EXPENSE_CATEGORIES, ExpenseCategory
    from apps.inventory.models import Warehouse

    tenant = Tenant.objects.create(name=name, slug=_unique_slug(name), phone=phone)
    branch = Branch.objects.create(tenant=tenant, name="Asosiy filial")
    Warehouse.objects.create(tenant=tenant, branch=branch, name="Asosiy ombor")

    roles = {
        spec["name"]: Role.objects.create(
            tenant=tenant,
            name=spec["name"],
            permissions=spec["permissions"],
            max_discount_percent=spec["max_discount_percent"],
            is_system=True,
        )
        for spec in DEFAULT_ROLES
    }

    Unit.objects.bulk_create(
        [Unit(tenant=tenant, name=n, short=s, allow_fraction=f) for n, s, f in DEFAULT_UNITS]
    )
    PriceType.objects.bulk_create(
        [
            PriceType(tenant=tenant, name=n, is_default=d, sort=i)
            for i, (n, d) in enumerate(DEFAULT_PRICE_TYPES)
        ]
    )

    ExpenseCategory.objects.bulk_create(
        [ExpenseCategory(tenant=tenant, name=n) for n in DEFAULT_EXPENSE_CATEGORIES]
    )

    owner = User.objects.create_user(
        username=owner_username,
        password=owner_password,
        tenant=tenant,
        first_name=owner_first_name,
        phone=phone,
    )
    owner.roles.add(roles["Egasi"])

    audit.record(
        action="tenant.provision",
        entity="tenant",
        entity_id=tenant.pk,
        tenant=tenant,
        after={"name": name, "owner": owner_username},
    )
    return ProvisionResult(tenant=tenant, branch=branch, owner=owner)
