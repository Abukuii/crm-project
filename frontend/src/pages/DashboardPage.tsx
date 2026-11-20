import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, DollarSign, Package, ShoppingCart } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { CurrentRate, PaginatedProducts } from "@/api/types";
import { Card, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/format";
import { useAuth } from "@/stores/auth";

function Kpi({ icon, label, value, hint, loading }: {
  icon: ReactNode; label: string; value: ReactNode; hint?: ReactNode; loading?: boolean;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-sm text-muted">
        <span>{label}</span>
        <span className="rounded-lg bg-brand-soft p-2 text-brand">{icon}</span>
      </div>
      <div className="mt-3 text-2xl font-semibold num">{loading ? <Skeleton className="h-8 w-28" /> : value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </Card>
  );
}

export function DashboardPage() {
  const { user, can } = useAuth();

  const rate = useQuery({
    queryKey: ["rate", "USD"],
    queryFn: () => api<CurrentRate>("/currency/rates/current/", { query: { currency: "USD" } }),
    retry: false,
  });
  const products = useQuery({
    queryKey: ["products", "count"],
    queryFn: () => api<PaginatedProducts>("/catalog/products/", { query: { page_size: 1, is_archived: false } }),
    enabled: can("catalog.view"),
  });
  const lowStock = useQuery({
    queryKey: ["balances", "low", "count"],
    queryFn: () => api<{ count: number }>("/inventory/balances/", { query: { low_stock: true, page_size: 1 } }),
    enabled: can("inventory.view"),
  });

  const rateMissing = rate.error instanceof ApiError && rate.error.code === "rate_not_found";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Xush kelibsiz, {user?.first_name || user?.username}!</h1>
        <p className="text-sm text-muted">{user?.tenant?.name}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          icon={<ShoppingCart className="h-4 w-4" />}
          label="Bugungi savdo"
          value={formatMoney(0)}
          hint="Kassa moduli keyingi bosqichda"
        />
        <Kpi
          icon={<Package className="h-4 w-4" />}
          label="Faol mahsulotlar"
          loading={products.isLoading}
          value={formatNumber(products.data?.count ?? 0)}
          hint={<Link to="/products" className="text-brand hover:underline">Katalogga o'tish →</Link>}
        />
        <Kpi
          icon={<AlertTriangle className="h-4 w-4" />}
          label="Kam qolganlar"
          loading={lowStock.isLoading}
          value={formatNumber(lowStock.data?.count ?? 0)}
          hint={<Link to="/stock?low_stock=true" className="text-brand hover:underline">Ro'yxatni ko'rish →</Link>}
        />
        <Kpi
          icon={<DollarSign className="h-4 w-4" />}
          label="Dollar kursi"
          loading={rate.isLoading}
          value={rateMissing ? "—" : formatMoney(rate.data?.rate)}
          hint={
            rateMissing
              ? "Kurs hali kiritilmagan"
              : rate.data && `${rate.data.date} · ${rate.data.source === "cbu" ? "Markaziy bank" : "Do'kon kursi"}`
          }
        />
      </div>
    </div>
  );
}
