import { useQuery } from "@tanstack/react-query";

import type {
  Category,
  CurrentRate,
  ExpenseCategory,
  PriceType,
  Role,
  Unit,
  Warehouse,
} from "@/api/types";
import { locale } from "@/i18n";
import { api } from "@/lib/api";

const LONG = 5 * 60_000;

export const useWarehouses = () =>
  useQuery({ queryKey: ["warehouses"], queryFn: () => api<Warehouse[]>("/inventory/warehouses/"), staleTime: LONG });

export const useUnits = () =>
  useQuery({ queryKey: ["units"], queryFn: () => api<Unit[]>("/catalog/units/"), staleTime: LONG });

export const useCategories = () =>
  useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/catalog/categories/"), staleTime: LONG });

export const usePriceTypes = () =>
  useQuery({ queryKey: ["price-types"], queryFn: () => api<PriceType[]>("/catalog/price-types/"), staleTime: LONG });

export const useExpenseCategories = () =>
  useQuery({
    queryKey: ["expense-categories"],
    queryFn: () => api<ExpenseCategory[]>("/finance/expense-categories/"),
    staleTime: LONG,
  });

export const useRoles = () =>
  useQuery({ queryKey: ["roles"], queryFn: () => api<{ results: Role[] }>("/accounts/roles/").then((r) => r.results) });

export const useUsdRate = () =>
  useQuery({
    queryKey: ["rate", "USD"],
    queryFn: () => api<CurrentRate>("/currency/rates/current/", { query: { currency: "USD" } }),
    retry: false,
  });

/** YYYY-MM-DD (mahalliy vaqt bo'yicha). */
export function isoDate(d = new Date()): string {
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export function monthStart(): string {
  const d = new Date();
  return isoDate(new Date(d.getFullYear(), d.getMonth(), 1));
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(locale(), { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [y, m, d] = value.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}
