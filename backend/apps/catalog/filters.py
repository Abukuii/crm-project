import django_filters
from django.db.models import Q

from apps.core.text import normalize, search_key

from .models import Category, Product


def _descendant_ids(category_id: int, tenant_id: int) -> list[int]:
    ids, frontier = [category_id], [category_id]
    while frontier:
        frontier = list(
            Category.objects.filter(tenant_id=tenant_id, parent_id__in=frontier).values_list(
                "id", flat=True
            )
        )
        ids.extend(frontier)
    return ids


class ProductFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    category = django_filters.NumberFilter(method="filter_category")
    is_archived = django_filters.BooleanFilter()
    brand = django_filters.NumberFilter()
    price_currency = django_filters.CharFilter()

    class Meta:
        model = Product
        fields = ["is_archived", "brand", "price_currency"]

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        words = normalize(value).split()
        cond = Q()
        for word in words:
            cond &= Q(search_text__contains=word)
        compact = search_key(value)
        if compact:
            cond |= Q(search_text__contains=compact)
        cond |= Q(sku__iexact=value) | Q(barcodes__code=value)
        return queryset.filter(cond).distinct()

    def filter_category(self, queryset, name, value):
        tenant_id = self.request.user.tenant_id
        return queryset.filter(category_id__in=_descendant_ids(value, tenant_id))
