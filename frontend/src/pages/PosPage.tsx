import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CornerDownLeft, Loader2, Minus, PackageSearch, Plus, Printer, ScanBarcode, Search, Trash2, UserPlus, UserRound, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { create } from "zustand";

import { t } from "@/i18n";
import { PAYMENT_LABELS, type Customer, type Page, type PosProduct, type Sale } from "@/api/types";
import { Modal } from "@/components/overlay";
import { Badge, Button, Card, EmptyState, Input, Select } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, formatNumber, formatQty } from "@/lib/format";
import { formatDateTime, isoDate, useWarehouses } from "@/lib/queries";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

interface CartLine {
  key: string;
  product: PosProduct;
  unitIdx: number;
  qty: string;
  price: string; // kelishilgan narx (1 birlik)
}

type Method = "cash" | "card" | "transfer" | "credit";
const METHODS: Method[] = ["cash", "card", "transfer", "credit"];

const n = (v: string | number | undefined | null) => Number(v || 0);

/** Skaner uchun qisqa ovozli signal: muvaffaqiyat — baland, xato — past. */
let audioCtx: AudioContext | null = null;
function beep(ok = true) {
  try {
    audioCtx ??= new AudioContext();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.value = ok ? 1320 : 220;
    gain.gain.value = 0.06;
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + (ok ? 0.08 : 0.25));
  } catch {
    /* ovoz ixtiyoriy */
  }
}

/** Kod (shtrix-kod / QR / artikul) bo'yicha mahsulot va birlik indeksini topish. */
function matchCode(items: PosProduct[], code: string): { product: PosProduct; unitIdx: number } | null {
  for (const p of items) {
    const idx = p.units.findIndex((u) => u.barcodes.includes(code));
    if (idx >= 0) return { product: p, unitIdx: idx };
  }
  const bySku = items.find((p) => p.sku === code);
  return bySku ? { product: bySku, unitIdx: 0 } : null;
}
const round2 = (v: number) => Math.round(v * 100) / 100;

function lineTotal(l: CartLine) {
  return round2(n(l.qty) * n(l.price));
}

/* ── Mijoz tanlash ──────────────────────────────────────────────────────── */
function CustomerPicker({ value, onChange }: { value: Customer | null; onChange: (c: Customer | null) => void }) {
  const { can } = useAuth();
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "" });
  const debounced = useDebounced(term);
  const list = useQuery({
    queryKey: ["customers", "pick", debounced],
    queryFn: () => api<Page<Customer>>("/sales/customers/", { query: { search: debounced, page_size: 8, is_archived: false } }),
    enabled: open,
  });
  const create = useMutation({
    mutationFn: () => api<Customer>("/sales/customers/", { method: "POST", body: form }),
    onSuccess: (c) => {
      onChange(c);
      setCreating(false);
      setForm({ name: "", phone: "" });
      toast.success(t("Mijoz qo'shildi"));
    },
    onError: toast.error,
  });

  if (value) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2 px-3 py-2">
        <UserRound className="h-5 w-5 text-brand" />
        <div className="min-w-0 flex-1 text-sm">
          <p className="truncate font-medium">{value.name}</p>
          <p className="text-xs text-muted">
            {value.phone || t("telefon yo'q")}
            {Number(value.debt) > 0 && <span className="text-danger"> · qarz {formatMoney(value.debt)}</span>}
          </p>
        </div>
        <button onClick={() => onChange(null)} className="text-muted hover:text-fg" aria-label={t("Mijozni olib tashlash")}>
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="flex gap-2">
        <div className="flex-1">
          <Input
            placeholder={t("Mijoz: ism yoki telefon")}
            icon={<UserRound className="h-4 w-4" />}
            value={term}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            onChange={(e) => setTerm(e.target.value)}
            aria-label={t("Mijoz qidirish")}
          />
        </div>
        {can("customers.manage") && (
          <Button variant="secondary" size="icon" className="h-10 w-10" onClick={() => setCreating(true)} title={t("Yangi mijoz")} aria-label={t("Yangi mijoz")}>
            <UserPlus className="h-4 w-4" />
          </Button>
        )}
      </div>
      {open && (list.data?.results.length ?? 0) > 0 && (
        <ul className="anim-pop absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-xl border border-border bg-surface p-1 shadow-xl">
          {list.data!.results.map((c) => (
            <li key={c.id}>
              <button
                className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2"
                onMouseDown={() => (onChange(c), setTerm(""))}
              >
                <span>
                  {c.name} <span className="text-muted">{c.phone}</span>
                </span>
                {Number(c.debt) > 0 && <Badge tone="danger">{formatNumber(c.debt, 0)}</Badge>}
              </button>
            </li>
          ))}
        </ul>
      )}
      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t("Yangi mijoz")}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreating(false)}>{t("Bekor")}</Button>
            <Button loading={create.isPending} disabled={!form.name.trim()} onClick={() => create.mutate()}>{t("Saqlash")}</Button>
          </>
        }
      >
        <div className="space-y-3">
          <Input label={t("Ism familiya")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
          <Input label={t("Telefon")} value={form.phone} inputMode="tel" placeholder="+998 90 123 45 67" onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        </div>
      </Modal>
    </div>
  );
}

/* ── Chek ───────────────────────────────────────────────────────────────── */
export function Receipt({ sale, tenantName }: { sale: Sale; tenantName?: string }) {
  return (
    <div className="print-area mx-auto max-w-[320px] font-mono text-[12px] leading-relaxed">
      <p className="text-center text-sm font-bold">{tenantName ?? "Savdo"}</p>
      <p className="text-center">Chek #{sale.number}</p>
      <p className="text-center">{formatDateTime(sale.created_at)}</p>
      <p className="text-center">Kassir: {sale.cashier_name}</p>
      {sale.customer_name && <p className="text-center">Mijoz: {sale.customer_name}</p>}
      <hr className="my-2 border-dashed border-current" />
      {sale.lines.map((l) => (
        <div key={l.id}>
          <p>{l.product_name}</p>
          <p className="flex justify-between">
            <span>{formatNumber(l.qty, 3)} {l.unit_short} × {formatNumber(l.price, 0)}</span>
            <span>{formatNumber(l.total, 0)}</span>
          </p>
        </div>
      ))}
      <hr className="my-2 border-dashed border-current" />
      {Number(sale.discount_total) > 0 && (
        <p className="flex justify-between"><span>{t("Chegirma")}</span><span>{formatNumber(sale.discount_total, 0)}</span></p>
      )}
      <p className="flex justify-between text-sm font-bold"><span>{t("JAMI")}</span><span>{formatNumber(sale.total, 0)} so'm</span></p>
      {sale.payments.map((p) => (
        <p key={p.method} className="flex justify-between"><span>{t(PAYMENT_LABELS[p.method] ?? p.method)}</span><span>{formatNumber(p.amount, 0)}</span></p>
      ))}
      <hr className="my-2 border-dashed border-current" />
      <p className="text-center">{t("Xaridingiz uchun rahmat!")}</p>
    </div>
  );
}

/* ── To'lov oynasi ──────────────────────────────────────────────────────── */
function PaymentModal({
  open,
  onClose,
  total,
  customer,
  onSubmit,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  total: number;
  customer: Customer | null;
  onSubmit: (payments: { method: Method; amount: string }[], dueDate: string | null) => void;
  loading: boolean;
}) {
  const [amounts, setAmounts] = useState<Record<Method, string>>({ cash: "", card: "", transfer: "", credit: "" });
  const [received, setReceived] = useState("");
  const [due, setDue] = useState("");

  useEffect(() => {
    if (open) {
      setAmounts({ cash: String(total), card: "", transfer: "", credit: "" });
      setReceived("");
      setDue("");
    }
  }, [open, total]);

  const paid = round2(METHODS.reduce((s, m) => s + n(amounts[m]), 0));
  const left = round2(total - paid);
  const change = n(received) > n(amounts.cash) ? round2(n(received) - n(amounts.cash)) : 0;
  const creditWithoutCustomer = n(amounts.credit) > 0 && !customer;

  const setOnly = (m: Method) => setAmounts({ cash: "", card: "", transfer: "", credit: "", [m]: String(total) });
  const fillRest = (m: Method) => setAmounts((a) => ({ ...a, [m]: String(round2(n(a[m]) + left)) }));

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("To'lov")}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("Bekor (Esc)")}</Button>
          <Button
            className="min-w-40"
            loading={loading}
            disabled={left !== 0 || creditWithoutCustomer}
            onClick={() =>
              onSubmit(
                METHODS.filter((m) => n(amounts[m]) > 0).map((m) => ({ method: m, amount: String(n(amounts[m])) })),
                n(amounts.credit) > 0 && due ? due : null,
              )
            }
          >
            Sotish · {formatMoney(total)}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="rounded-xl bg-surface-2 p-4 text-center">
          <p className="text-sm text-muted">{t("To'lanadigan summa")}</p>
          <p className="text-3xl font-bold num">{formatMoney(total)}</p>
        </div>
        <div className="grid grid-cols-4 gap-2">
          {METHODS.map((m) => (
            <Button key={m} variant={n(amounts[m]) === total ? "primary" : "secondary"} size="sm" onClick={() => setOnly(m)}>
              {t(PAYMENT_LABELS[m] ?? m)}
            </Button>
          ))}
        </div>
        <div className="space-y-2">
          {METHODS.map((m) => (
            <div key={m} className="flex items-end gap-2">
              <div className="flex-1">
                <Input
                  label={t(PAYMENT_LABELS[m] ?? m)}
                  type="number"
                  inputMode="decimal"
                  min={0}
                  value={amounts[m]}
                  onChange={(e) => setAmounts({ ...amounts, [m]: e.target.value })}
                />
              </div>
              {left > 0 && (
                <Button variant="ghost" size="sm" className="mb-1" onClick={() => fillRest(m)}>{t("+ qoldiq")}</Button>
              )}
            </div>
          ))}
        </div>
        {n(amounts.cash) > 0 && (
          <div className="grid grid-cols-2 gap-3 rounded-xl border border-border p-3">
            <Input label={t("Mijoz bergan naqd")} type="number" inputMode="decimal" value={received} onChange={(e) => setReceived(e.target.value)} />
            <div>
              <p className="text-sm font-medium">{t("Qaytim")}</p>
              <p className="mt-2 text-xl font-semibold text-success num">{formatMoney(change)}</p>
            </div>
          </div>
        )}
        {n(amounts.credit) > 0 && (
          <div className="space-y-2 rounded-xl border border-warning/40 bg-warning/5 p-3">
            {creditWithoutCustomer ? (
              <p className="text-sm text-danger">{t("Nasiya uchun mijozni tanlang")}</p>
            ) : (
              <Input label={t("To'lov muddati (ixtiyoriy)")} type="date" min={isoDate()} value={due} onChange={(e) => setDue(e.target.value)} />
            )}
          </div>
        )}
        <p className={cn("text-center text-sm font-medium", left === 0 ? "text-success" : "text-danger")}>
          {left === 0 ? t("Summa to'g'ri") : left > 0 ? t("Yana {sum} kerak", { sum: formatMoney(left) }) : t("{sum} ortiqcha", { sum: formatMoney(-left) })}
        </p>
      </div>
    </Modal>
  );
}

/* ── Kassa ──────────────────────────────────────────────────────────────── */
type Updater<T> = T | ((prev: T) => T);

/** Kassa savati: komponent qayta yaratilganda ham saqlanadi. */
const usePosCart = create<{
  cart: CartLine[];
  customer: Customer | null;
  setCart: (u: Updater<CartLine[]>) => void;
  setCustomer: (c: Customer | null) => void;
}>((set) => ({
  cart: [],
  customer: null,
  setCart: (u) => set((s) => ({ cart: typeof u === "function" ? u(s.cart) : u })),
  setCustomer: (customer) => set({ customer }),
}));

export function PosPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const warehouses = useWarehouses();
  const [warehouseId, setWarehouseId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  // Savat va mijoz alohida store'da — til almashganda yoki sahifadan chiqib qaytganda yo'qolmaydi
  const { cart, setCart, customer, setCustomer } = usePosCart();
  const [paying, setPaying] = useState(false);
  const [done, setDone] = useState<Sale | null>(null);
  const [active, setActive] = useState(-1);
  const [scanning, setScanning] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const debounced = useDebounced(search.trim(), 200);

  useEffect(() => {
    const first = warehouses.data?.find((w) => w.is_active);
    if (warehouseId === null && first) setWarehouseId(first.id);
  }, [warehouses.data, warehouseId]);

  const catalog = useQuery({
    queryKey: ["pos-catalog", warehouseId, debounced, customer?.id],
    queryFn: ({ signal }) =>
      api<PosProduct[]>("/sales/sales/pos-catalog/", {
        query: { warehouse: warehouseId, search: debounced, customer: customer?.id, limit: 48 },
        signal,
      }),
    // Mahsulotlar faqat qidiruvga yozilganda ko'rsatiladi
    enabled: warehouseId !== null && debounced.length > 0,
    placeholderData: (prev) => prev,
  });
  const showList = search.trim().length > 0;
  const results = showList ? (catalog.data ?? []) : [];

  useEffect(() => setActive(-1), [debounced]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  // Mijoz o'zgarsa narx turi ham o'zgarishi mumkin — savatdagi ro'yxat narxlarini yangilaymiz
  useEffect(() => {
    if (!catalog.data) return;
    setCart((lines) =>
      lines.map((l) => {
        const fresh = catalog.data!.find((p) => p.id === l.product.id);
        return fresh ? { ...l, product: fresh, price: String(Number(fresh.units[l.unitIdx]?.price ?? l.price)) } : l;
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customer?.id]);

  const addProduct = (p: PosProduct, unitIdx = 0) => {
    setSearch("");
    setActive(-1);
    searchRef.current?.focus();
    setCart((lines) => {
      const existing = lines.find((l) => l.product.id === p.id && l.unitIdx === unitIdx);
      if (existing) return lines.map((l) => (l === existing ? { ...l, qty: String(n(l.qty) + 1) } : l));
      return [...lines, { key: `${p.id}-${unitIdx}-${Date.now()}`, product: p, unitIdx, qty: "1", price: String(Number(p.units[unitIdx]!.price)) }];
    });
  };

  /** Enter: skaner kodi (aniq moslik) → darhol savatga; aks holda tanlangan yoki yagona natija. */
  const onSearchEnter = async () => {
    const term = search.trim();
    if (!term || warehouseId === null) return;
    if (active >= 0 && results[active] && debounced === term) {
      addProduct(results[active]!);
      return;
    }
    setScanning(true);
    try {
      const items = await qc.fetchQuery({
        queryKey: ["pos-catalog", warehouseId, term, customer?.id],
        queryFn: () =>
          api<PosProduct[]>("/sales/sales/pos-catalog/", {
            query: { warehouse: warehouseId, search: term, customer: customer?.id, limit: 48 },
          }),
        staleTime: 10_000,
      });
      const hit = matchCode(items, term) ?? (items.length === 1 ? { product: items[0]!, unitIdx: 0 } : null);
      if (hit) {
        addProduct(hit.product, hit.unitIdx);
        beep(true);
        toast.success(`+ ${hit.product.name} (${hit.product.units[hit.unitIdx]!.unit_short})`);
      } else {
        beep(false);
        if (!items.length) toast.error(t("Mahsulot topilmadi") + ": " + term);
        else setActive(0);
      }
    } catch (e) {
      beep(false);
      toast.error(e);
    } finally {
      setScanning(false);
    }
  };

  const onSearchKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void onSearchEnter();
    } else if (e.key === "ArrowDown" && results.length) {
      e.preventDefault();
      setActive((i) => Math.min(results.length - 1, i + 1));
    } else if (e.key === "ArrowUp" && results.length) {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Escape") {
      setSearch("");
    }
  };

  const totals = useMemo(() => {
    let subtotal = 0;
    let total = 0;
    for (const l of cart) {
      const list = n(l.product.units[l.unitIdx]?.price);
      subtotal += list * n(l.qty);
      total += lineTotal(l);
    }
    return { subtotal: round2(subtotal), total: round2(total), discount: round2(subtotal - total) };
  }, [cart]);

  const overStock = cart.filter((l) => n(l.qty) * n(l.product.units[l.unitIdx]?.factor) > n(l.product.stock));

  const sell = useMutation({
    mutationFn: ({ payments, due }: { payments: { method: Method; amount: string }[]; due: string | null }) =>
      api<Sale>("/sales/sales/", {
        method: "POST",
        body: {
          client_uuid: crypto.randomUUID(),
          warehouse: warehouseId,
          customer: customer?.id ?? null,
          due_date: due,
          items: cart.map((l) => ({
            product: l.product.id,
            unit: l.product.units[l.unitIdx]!.unit,
            qty: l.qty,
            price: n(l.price) !== n(l.product.units[l.unitIdx]?.price) ? l.price : null,
          })),
          payments,
        },
      }),
    onSuccess: (sale) => {
      setPaying(false);
      setDone(sale);
      setCart([]);
      setCustomer(null);
      toast.success(t("Savdo #{n} — {sum}", { n: sale.number, sum: formatMoney(sale.total) }));
      void qc.invalidateQueries({ queryKey: ["pos-catalog"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: toast.error,
  });

  // Klaviatura: F2 — qidiruv, F9 — to'lov
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "F2") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (e.key === "F9" && cart.length) {
        e.preventDefault();
        setPaying(true);
      } else if (!paying && !done && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        // Fokus hech qaysi maydonda bo'lmasa — skaner/klaviatura kiritishi qidiruvga tushadi
        const el = document.activeElement as HTMLElement | null;
        const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
        if (!typing) searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cart.length, paying, done]);

  const update = (key: string, patch: Partial<CartLine>) =>
    setCart((lines) => lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  return (
    <div className="mx-auto grid max-w-[1600px] gap-4 lg:h-[calc(100dvh-7.5rem)] lg:grid-cols-[minmax(0,1fr)_360px] xl:grid-cols-[minmax(0,1fr)_420px]">
      {/* Katalog: faqat qidiruvda, qator ko'rinishida */}
      <section className="flex min-h-0 min-w-0 flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <div className="relative min-w-60 flex-1">
            <Input
              ref={searchRef}
              autoFocus
              placeholder={t("Shtrix-kod / QR-kodni skanerlang yoki nomini yozing (F2)")}
              icon={scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanBarcode className="h-4 w-4" />}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={onSearchKey}
              aria-label={t("Mahsulot qidirish")}
              className="h-12 text-base"
              autoComplete="off"
            />
            {search && (
              <button onClick={() => (setSearch(""), searchRef.current?.focus())} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-fg" aria-label={t("Tozalash")}>
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          {(warehouses.data?.length ?? 0) > 1 && (
            <div className="w-48">
              <Select value={warehouseId ?? ""} onChange={(e) => setWarehouseId(Number(e.target.value))} aria-label={t("Ombor")} className="h-12">
                {warehouses.data!.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          {!showList ? (
            <div className="anim-fade flex h-full min-h-64 flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed border-border p-8 text-center">
              <div className="relative">
                <span className="anim-ping absolute inset-0 rounded-2xl bg-brand/20" />
                <div className="relative grid h-16 w-16 place-items-center rounded-2xl bg-brand-soft text-brand">
                  <ScanBarcode className="h-8 w-8" />
                </div>
              </div>
              <div>
                <p className="text-lg font-semibold">{t("Skanerlang yoki qidiring")}</p>
                <p className="mt-1 text-sm text-muted">{t("Shtrix-kod yoki QR-kod o'qilganda mahsulot avtomatik savatga qo'shiladi")}</p>
              </div>
              <div className="flex flex-wrap justify-center gap-2 text-xs text-muted">
                <span className="rounded-md border border-border px-2 py-1"><b>F2</b> {t("qidiruv")}</span>
                <span className="rounded-md border border-border px-2 py-1"><b>↑ ↓</b> {t("tanlash")}</span>
                <span className="rounded-md border border-border px-2 py-1"><b>{t("Enter")}</b> {t("savatga")}</span>
                <span className="rounded-md border border-border px-2 py-1"><b>F9</b> {t("to'lov")}</span>
              </div>
            </div>
          ) : catalog.isFetching && !results.length ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }, (_, i) => <div key={i} className="h-16 animate-pulse rounded-xl bg-surface-2" />)}
            </div>
          ) : !results.length ? (
            <Card><EmptyState icon={<PackageSearch className="h-6 w-6" />} title={t("Mahsulot topilmadi")} hint={t("Narxi belgilanmagan yoki arxivlangan mahsulotlar kassada ko'rinmaydi")} /></Card>
          ) : (
            <Card className="overflow-hidden">
              <ul ref={listRef} className={cn("divide-y divide-border", catalog.isFetching && "opacity-70")} role="listbox" aria-label={t("Topilgan mahsulotlar")}>
                {results.map((p, i) => {
                  const stock = n(p.stock);
                  const base = p.units[0]!;
                  return (
                    <li key={p.id} data-idx={i} role="option" aria-selected={i === active}>
                      <div
                        className={cn(
                          "group flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors",
                          i === active ? "bg-brand-soft" : "hover:bg-surface-2/70",
                        )}
                        onMouseEnter={() => setActive(i)}
                        onClick={() => addProduct(p)}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{p.name}</p>
                          <p className="truncate text-xs text-muted">
                            <span className={cn("font-medium", stock <= 0 ? "text-danger" : stock < 10 ? "text-warning" : "text-success")}>
                              {formatQty(p.stock, base.unit_short)}
                            </span>
                            {" · "}
                            {p.sku}
                            {p.category && <> · {p.category}</>}
                          </p>
                        </div>
                        {p.units.length > 1 && (
                          <div className="hidden shrink-0 gap-1 xl:flex">
                            {p.units.slice(1).map((u, ui) => (
                              <button
                                key={u.unit}
                                onClick={(e) => (e.stopPropagation(), addProduct(p, ui + 1))}
                                className="rounded-md border border-border px-2 py-0.5 text-xs hover:border-brand hover:text-brand"
                                title={`1 ${u.unit_short} = ${Number(u.factor)} ${base.unit_short} · ${formatMoney(u.price)}`}
                              >
                                +{u.unit_short}
                              </button>
                            ))}
                          </div>
                        )}
                        <span className="shrink-0 whitespace-nowrap text-right font-semibold text-brand num">{formatMoney(base.price)}</span>
                        <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg transition-colors", i === active ? "bg-brand text-on-brand" : "bg-surface-2 text-muted group-hover:text-fg")}>
                          {i === active ? <CornerDownLeft className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}
        </div>
      </section>

      {/* Savat */}
      <Card className="flex min-h-[420px] flex-col overflow-hidden">
        <div className="space-y-3 border-b border-border p-4">
          <CustomerPicker value={customer} onChange={setCustomer} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {!cart.length ? (
            <EmptyState icon={<Search className="h-6 w-6" />} title={t("Savat bo'sh")} hint={t("Mahsulotni bosing yoki shtrix-kodni skanerlang")} />
          ) : (
            <ul className="divide-y divide-border">
              {cart.map((l) => {
                const unit = l.product.units[l.unitIdx]!;
                const discounted = n(l.price) < n(unit.price);
                return (
                  <li key={l.key} className="anim-slide-up space-y-2 p-3">
                    <div className="flex items-start gap-2">
                      <p className="flex-1 text-sm font-medium">{l.product.name}</p>
                      <button onClick={() => setCart((c) => c.filter((x) => x.key !== l.key))} className="text-muted hover:text-danger" aria-label={t("O'chirish")}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center rounded-lg border border-border">
                        <button className="px-2 py-1.5 text-muted hover:text-fg" onClick={() => update(l.key, { qty: String(Math.max(0, n(l.qty) - 1)) })} aria-label={t("Kamaytirish")}>
                          <Minus className="h-3.5 w-3.5" />
                        </button>
                        <input
                          className="w-16 bg-transparent text-center text-sm num focus:outline-none"
                          inputMode="decimal"
                          value={l.qty}
                          onChange={(e) => update(l.key, { qty: e.target.value.replace(",", ".") })}
                          aria-label={t("Miqdor")}
                        />
                        <button className="px-2 py-1.5 text-muted hover:text-fg" onClick={() => update(l.key, { qty: String(n(l.qty) + 1) })} aria-label={t("Ko'paytirish")}>
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      {l.product.units.length > 1 ? (
                        <select
                          className="h-8 rounded-lg border border-border bg-surface px-2 text-sm"
                          value={l.unitIdx}
                          onChange={(e) => {
                            const idx = Number(e.target.value);
                            update(l.key, { unitIdx: idx, price: String(Number(l.product.units[idx]!.price)) });
                          }}
                          aria-label={t("Birlik")}
                        >
                          {l.product.units.map((u, i) => <option key={u.unit} value={i}>{u.unit_short}</option>)}
                        </select>
                      ) : (
                        <span className="text-sm text-muted">{unit.unit_short}</span>
                      )}
                      <span className="text-muted">×</span>
                      <input
                        className={cn(
                          "h-8 w-28 rounded-lg border bg-surface px-2 text-right text-sm num focus:border-brand focus:outline-none",
                          discounted ? "border-warning text-warning" : "border-border",
                        )}
                        inputMode="decimal"
                        value={l.price}
                        onChange={(e) => update(l.key, { price: e.target.value.replace(",", ".") })}
                        title={t("Kelishilgan narx")}
                        aria-label={t("Narx")}
                      />
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-muted">
                        {discounted && <>{t("Asl narx")} {formatNumber(unit.price, 0)} · </>}
                        {t("qoldiq")} {formatQty(n(l.product.stock) / n(unit.factor), unit.unit_short)}
                      </span>
                      <span className="text-sm font-semibold num">{formatMoney(lineTotal(l))}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div className="space-y-2 border-t border-border bg-surface-2/60 p-4">
          {totals.discount > 0 && (
            <>
              <div className="flex justify-between text-sm text-muted"><span>{t("Narxlar bo'yicha")}</span><span className="num">{formatMoney(totals.subtotal)}</span></div>
              <div className="flex justify-between text-sm text-warning"><span>{t("Chegirma")}</span><span className="num">−{formatMoney(totals.discount)}</span></div>
            </>
          )}
          <div className="flex items-end justify-between">
            <span className="text-sm text-muted">{t("Jami")}</span>
            <span className="text-3xl font-bold num">{formatMoney(totals.total)}</span>
          </div>
          {overStock.length > 0 && (
            <p className="text-xs text-danger">Qoldiq yetmaydi: {overStock.map((l) => l.product.name).join(", ")}</p>
          )}
          <Button className="h-12 w-full text-base" disabled={!cart.length || totals.total <= 0} onClick={() => setPaying(true)}>
            {t("To'lov (F9)")}
          </Button>
        </div>
      </Card>

      <PaymentModal
        open={paying}
        onClose={() => setPaying(false)}
        total={totals.total}
        customer={customer}
        loading={sell.isPending}
        onSubmit={(payments, due) => sell.mutate({ payments, due })}
      />

      <Modal
        open={!!done}
        onClose={() => (setDone(null), searchRef.current?.focus())}
        title={t("Savdo #{n} yakunlandi", { n: done?.number })}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> {t("Chek")}</Button>
            <Button onClick={() => (setDone(null), searchRef.current?.focus())}>{t("Yangi savdo")}</Button>
          </>
        }
      >
        {done && <Receipt sale={done} tenantName={user?.tenant?.name} />}
      </Modal>
    </div>
  );
}
