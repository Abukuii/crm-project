"""Ruxsatlar reyestri. Rol — shu kodlar to'plami. "*" — barcha ruxsatlar (egasi)."""

ALL = "*"

PERMISSIONS: dict[str, str] = {
    "catalog.view": "Katalogni ko'rish",
    "catalog.manage": "Mahsulot, kategoriya, birliklarni boshqarish",
    "price.edit": "Narx va valyuta kursini o'zgartirish",
    "cost.view": "Tannarx va foydani ko'rish",
    "inventory.view": "Qoldiqlarni ko'rish",
    "inventory.manage": "Kirim, ko'chirish, hisobdan chiqarish",
    "inventory.audit": "Inventarizatsiyani tasdiqlash",
    "sales.create": "Sotish (kassa)",
    "sales.refund": "Qaytarish",
    "sales.discount_over_limit": "Limitdan ortiq chegirma",
    "customers.view": "Mijozlarni ko'rish",
    "customers.manage": "Mijozlarni boshqarish",
    "finance.view": "Moliyani ko'rish",
    "finance.manage": "Moliyaviy yozuvlar",
    "reports.view": "Hisobotlar",
    "users.manage": "Xodimlar va rollar",
    "settings.manage": "Sozlamalar",
    "audit.view": "Audit jurnali",
}

DEFAULT_ROLES = [
    {"name": "Egasi", "permissions": [ALL], "max_discount_percent": 100},
    {
        "name": "Menejer",
        "permissions": [
            "catalog.view", "catalog.manage", "price.edit", "inventory.view",
            "inventory.manage", "inventory.audit", "sales.create", "sales.refund",
            "sales.discount_over_limit", "customers.view", "customers.manage", "reports.view",
        ],
        "max_discount_percent": 15,
    },
    {
        "name": "Kassir",
        "permissions": ["catalog.view", "inventory.view", "sales.create", "customers.view"],
        "max_discount_percent": 5,
    },
    {
        "name": "Omborchi",
        "permissions": ["catalog.view", "inventory.view", "inventory.manage"],
        "max_discount_percent": 0,
    },
    {
        "name": "Buxgalter",
        "permissions": [
            "catalog.view", "cost.view", "inventory.view", "customers.view",
            "finance.view", "finance.manage", "reports.view",
        ],
        "max_discount_percent": 0,
    },
]  # fmt: skip
