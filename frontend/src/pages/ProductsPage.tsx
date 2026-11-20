import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Package, Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import type { PaginatedProducts } from "@/api/types";
import { Badge, Button, Card, EmptyState, Input, Skeleton } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";

const PAGE_SIZE = 50;

export function ProductsPage() {
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const page = Number(params.get("page") ?? "1");
  const debounced = useDebounced(search);

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["products", { search: debounced, page }],
    queryFn: ({ signal }) =>
      api<PaginatedProducts>("/catalog/products/", {
        query: { search: debounced, page, page_size: PAGE_SIZE, is_archived: false },
        signal,
      }),
    placeholderData: keepPreviousData,
  });

  const update = (next: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) (v ? p.set(k, v) : p.delete(k));
    setParams(p, { replace: true });
  };

  const pages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Mahsulotlar</h1>
          <p className="text-sm text-muted">{data ? `${data.count} ta mahsulot` : " "}</p>
        </div>
        <div className="w-full sm:w-80">
          <Input
            placeholder="Nomi, artikul yoki shtrix-kod…"
            icon={<Search className="h-4 w-4" />}
            value={search}
            onChange={(e) => update({ search: e.target.value || null, page: null })}
            aria-label="Mahsulot qidirish"
          />
        </div>
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10" />)}
          </div>
        ) : isError ? (
          <EmptyState icon={<Package className="h-6 w-6" />} title="Ma'lumotni yuklab bo'lmadi" hint="Internet aloqasini tekshiring" />
        ) : !data?.results.length ? (
          <EmptyState
            icon={<Package className="h-6 w-6" />}
            title={search ? "Hech narsa topilmadi" : "Hali mahsulot yo'q"}
            hint={search ? "Boshqa so'z bilan qidirib ko'ring (kirill va lotin farqi yo'q)" : "Mahsulot qo'shish va Excel import keyingi bosqichda"}
          />
        ) : (
          <div className={isFetching ? "opacity-60 transition-opacity" : undefined}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-surface-2 text-left text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Nomi</th>
                    <th className="px-4 py-3 font-medium">Artikul</th>
                    <th className="px-4 py-3 font-medium">Kategoriya</th>
                    <th className="px-4 py-3 font-medium">Birlik</th>
                    <th className="px-4 py-3 text-right font-medium">Narx</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.results.map((p) => {
                    const price = p.prices?.[0];
                    return (
                      <tr key={p.id} className="hover:bg-surface-2/60">
                        <td className="px-4 py-3 font-medium">{p.name}</td>
                        <td className="px-4 py-3 text-muted num">{p.sku}</td>
                        <td className="px-4 py-3">{p.category_name ?? <span className="text-muted">—</span>}</td>
                        <td className="px-4 py-3">
                          <Badge>{p.base_unit_short}</Badge>
                        </td>
                        <td className="px-4 py-3 text-right num">
                          {price ? formatMoney(price.amount, p.price_currency) : <span className="text-muted">—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {pages > 1 && (
              <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm">
                <span className="text-muted">{page} / {pages}</span>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })} aria-label="Oldingi sahifa">
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })} aria-label="Keyingi sahifa">
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
