import { t } from "@/i18n";
/** Raqamlarni o'zbekcha formatlash: 1 250 000, 2,5 (bo'shliq — minglik ajratgich). */

const NBSP = " ";

function group(intPart: string): string {
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

export function formatNumber(value: string | number | null | undefined, maxFraction = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  const negative = n < 0;
  const [intPart = "0", frac = ""] = Math.abs(n).toFixed(maxFraction).split(".");
  const trimmed = frac.replace(/0+$/, "");
  return `${negative ? "−" : ""}${group(intPart)}${trimmed ? `,${trimmed}` : ""}`;
}

export function formatMoney(value: string | number | null | undefined, currency = "UZS"): string {
  if (value === null || value === undefined || value === "") return "—";
  return currency === "USD" ? `$${formatNumber(value, 2)}` : `${formatNumber(value, 0)}${NBSP}${t("so'm")}`;
}

export function formatQty(value: string | number | null | undefined, unit?: string): string {
  const n = formatNumber(value, 3);
  return unit ? `${n}${NBSP}${unit}` : n;
}
