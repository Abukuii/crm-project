import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  DollarSign,
  Download,
  FileSpreadsheet,
  HandCoins,
  Pencil,
  Receipt,
  ShoppingCart,
  StickyNote,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { longDate, t, useLang, weekdayShort } from "@/i18n";
import { PAYMENT_LABELS, type Dashboard, type Reminder } from "@/api/types";
import { Modal } from "@/components/overlay";
import { Badge, Button, Card, Input, Skeleton } from "@/components/ui";
import { api, apiDownload } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, formatNumber } from "@/lib/format";
import { formatDate, formatDateTime, isoDate, monthStart, useUsdRate } from "@/lib/queries";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

function Delta({ now, before }: { now?: string; before?: string }) {
  const a = Number(now ?? 0);
  const b = Number(before ?? 0);
  if (!b) return null;
  const pct = ((a - b) / Math.abs(b)) * 100;
  const up = pct >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={cn("inline-flex items-center text-xs font-medium", up ? "text-success" : "text-danger")}>
      <Icon className="h-3.5 w-3.5" />
      {Math.abs(pct).toFixed(0)}%
    </span>
  );
}

function Kpi({ icon, label, value, hint }: { icon: ReactNode; label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <Card className="anim-slide-up p-4">
      <div>
        <div className="flex items-center justify-between text-sm text-muted">
          <span>{label}</span>
          <span className="rounded-lg bg-brand-soft p-2 text-brand">{icon}</span>
        </div>
        <div className="mt-3 text-2xl font-semibold num">{value}</div>
        {hint && <div className="mt-1 flex items-center gap-2 text-xs text-muted">{hint}</div>}
      </div>
    </Card>
  );
}

function WeekChart({ data }: { data: Dashboard["week"] }) {
  const max = Math.max(1, ...data.map((d) => Number(d.revenue)));
  return (
    <div className="flex h-48 items-end gap-2 sm:gap-3">
      {data.map((d, i) => {
        const h = (Number(d.revenue) / max) * 100;
        const date = new Date(d.date);
        return (
          <div key={d.date} className="group flex flex-1 flex-col items-center gap-2">
            <div className="relative flex h-40 w-full items-end">
              <div
                className="anim-bar w-full rounded-t-lg bg-gradient-to-t from-orange-600 to-amber-400 opacity-90 transition-opacity group-hover:opacity-100"
                style={{ height: `${Math.max(h, 2)}%`, animationDelay: `${i * 70}ms` }}
              />
              <span className="pointer-events-none absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-fg px-2 py-0.5 text-[11px] text-bg opacity-0 transition-opacity group-hover:opacity-100">
                {formatNumber(d.revenue, 0)}
              </span>
            </div>
            <span className="text-xs text-muted">
              {weekdayShort(date)} <span className="hidden sm:inline">{date.getDate()}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function RateCard() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const rate = useUsdRate();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const save = useMutation({
    mutationFn: () => api("/currency/rates/", { method: "POST", body: { currency: "USD", rate: value } }),
    onSuccess: () => {
      toast.success(t("Dollar kursi saqlandi"));
      setOpen(false);
      void qc.invalidateQueries({ queryKey: ["rate"] });
    },
    onError: toast.error,
  });
  return (
    <>
      <Kpi
        icon={<DollarSign className="h-4 w-4" />}
        label={t("Dollar kursi")}
        value={rate.isLoading ? <Skeleton className="h-8 w-28" /> : rate.data ? formatMoney(rate.data.rate) : "—"}
        hint={
          <>
            <span>{rate.data ? `${formatDate(rate.data.date)} · ${rate.data.source === "cbu" ? t("Markaziy bank") : t("Do'kon kursi")}` : t("Kiritilmagan")}</span>
            {can("price.edit") && (
              <button className="text-brand hover:underline" onClick={() => (setValue(rate.data?.rate ?? ""), setOpen(true))}>
                <Pencil className="inline h-3 w-3" /> {t("o'zgartirish")}
              </button>
            )}
          </>
        }
      />
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t("Do'kon dollar kursi")}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>{t("Bekor")}</Button>
            <Button loading={save.isPending} onClick={() => save.mutate()} disabled={!Number(value)}>{t("Saqlash")}</Button>
          </>
        }
      >
        <Input label={t("1 USD = ? so'm")} type="number" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
        <p className="mt-2 text-xs text-muted">
          {t("Do'kon kursi ishlatilishi uchun Sozlamalarda \"Kurs manbai: do'kon kursi\" ni tanlang.")}
        </p>
      </Modal>
    </>
  );
}

function RemindersWidget() {
  const { can } = useAuth();
  const q = useQuery({
    queryKey: ["reminders", "open"],
    queryFn: () => api<Reminder[]>("/notes/reminders/", { query: { is_done: false } }),
    enabled: can("reminders.manage"),
  });
  if (!can("reminders.manage")) return null;
  const tone = { urgent: "danger", important: "warning", normal: "neutral" } as const;
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold"><StickyNote className="h-4 w-4 text-brand" /> {t("Eslatmalar")}</h3>
        <Link to="/reminders" className="text-xs text-brand hover:underline">{t("Barchasi →")}</Link>
      </div>
      {q.data?.length ? (
        <ul className="space-y-2">
          {q.data.slice(0, 5).map((r) => (
            <li key={r.id} className="flex items-start gap-2 text-sm">
              <Badge tone={tone[r.level as keyof typeof tone] ?? "neutral"}>{r.level === "urgent" ? "!" : "•"}</Badge>
              <span className="flex-1">{r.text}</span>
              {r.due_date && <span className="text-xs text-muted">{formatDate(r.due_date)}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">{t("Hozircha eslatma yo'q")}</p>
      )}
    </Card>
  );
}

function StatsExportButton() {
  const [open, setOpen] = useState(false);
  const [range, setRange] = useState({ date_from: monthStart(), date_to: isoDate() });
  const [busy, setBusy] = useState(false);
  const presets: { label: string; from: string }[] = [
    { label: "Bugun", from: isoDate() },
    { label: "7 kun", from: isoDate(new Date(Date.now() - 6 * 864e5)) },
    { label: "Shu oy", from: monthStart() },
    { label: "30 kun", from: isoDate(new Date(Date.now() - 29 * 864e5)) },
  ];
  const download = async () => {
    setBusy(true);
    try {
      await apiDownload("/dataio/stats/export/", `statistika_${range.date_from}_${range.date_to}.xlsx`, {
        ...range,
        lang: useLang.getState().lang,
      });
      setOpen(false);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <FileSpreadsheet className="h-4 w-4" /> {t("Statistika (Excel)")}
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        size="sm"
        title={t("Umumiy statistikani yuklab olish")}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>{t("Bekor")}</Button>
            <Button loading={busy} disabled={!range.date_from || !range.date_to || range.date_from > range.date_to} onClick={() => void download()}>
              <Download className="h-4 w-4" /> {t("Yuklab olish")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {presets.map((p) => (
              <button
                key={p.label}
                onClick={() => setRange({ date_from: p.from, date_to: isoDate() })}
                className={cn(
                  "rounded-full px-3 py-1 text-sm",
                  range.date_from === p.from && range.date_to === isoDate() ? "bg-brand text-on-brand" : "bg-surface-2 text-muted hover:text-fg",
                )}
              >
                {t(p.label)}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input label={t("Dan")} type="date" value={range.date_from} onChange={(e) => setRange({ ...range, date_from: e.target.value })} />
            <Input label={t("Gacha")} type="date" value={range.date_to} onChange={(e) => setRange({ ...range, date_to: e.target.value })} />
          </div>
          <p className="text-xs text-muted">
            {t("Fayl varaqlari: umumiy ko'rsatkichlar, kunlar, mahsulotlar, to'lov turlari, kassirlar, xarajatlar va qarzdorlar.")}
          </p>
        </div>
      </Modal>
    </>
  );
}

export function DashboardPage() {
  const { user, can } = useAuth();
  const canReports = can("reports.view");
  const { data: d, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/reports/dashboard/"),
    enabled: canReports,
    refetchInterval: 60_000,
  });

  const greeting = (() => {
    const h = new Date().getHours();
    return h < 11 ? t("Xayrli tong") : h < 17 ? t("Xayrli kun") : t("Xayrli kech");
  })();

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="anim-slide-up">
          <h1 className="text-2xl font-semibold tracking-tight">{greeting}, {user?.first_name || user?.username}!</h1>
          <p className="text-sm text-muted">{user?.tenant?.name} · {longDate(new Date())}</p>
        </div>
        <div className="flex gap-2">
          {canReports && <StatsExportButton />}
          {can("sales.create") && (
            <Link to="/pos"><Button><ShoppingCart className="h-4 w-4" /> {t("Kassani ochish")}</Button></Link>
          )}
        </div>
      </div>

      {canReports && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi
            icon={<ShoppingCart className="h-4 w-4" />}
            label={t("Bugungi savdo")}
            value={isLoading ? <Skeleton className="h-8 w-32" /> : formatMoney(d?.today.revenue)}
            hint={d && <><span>{t("{n} ta chek", { n: d.today.sales_count })}</span>{Number(d.yesterday.revenue) > 0 && <><Delta now={d.today.revenue} before={d.yesterday.revenue} /><span>{t("kechagiga nisbatan")}</span></>}</>}
          />
          <Kpi
            icon={<TrendingUp className="h-4 w-4" />}
            label={d?.month.net_profit !== undefined ? t("Oylik sof foyda") : t("Oylik savdo")}
            value={isLoading ? <Skeleton className="h-8 w-32" /> : formatMoney(d?.month.net_profit ?? d?.month.revenue)}
            hint={d && (d.month.gross_profit !== undefined
              ? <span>{t("Yalpi")}: {formatMoney(d.month.gross_profit)} · {t("Xarajat")}: {formatMoney(d.month.expenses)}</span>
              : <><span>{t("{n} ta chek", { n: d.month.sales_count })}</span><Delta now={d.month.revenue} before={d.prev_month.revenue} /></>)}
          />
          <Kpi
            icon={<HandCoins className="h-4 w-4" />}
            label={t("Nasiya qarzlar")}
            value={isLoading ? <Skeleton className="h-8 w-32" /> : formatMoney(d?.debt.total)}
            hint={d && (
              <Link to="/customers?has_debt=true" className="hover:underline">
                {t("{n} ta qarzdor", { n: d.debt.debtors })}{Number(d.debt.overdue) > 0 && <span className="text-danger"> · {t("muddati o'tgan")} {formatMoney(d.debt.overdue)}</span>}
              </Link>
            )}
          />
          <RateCard />
        </div>
      )}

      {canReports && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="p-5 lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold">{t("Haftalik savdo")}</h3>
              {d && <span className="text-sm text-muted">{t("O'rtacha chek:")} <b className="text-fg num">{formatMoney(d.today.avg_check)}</b></span>}
            </div>
            {isLoading || !d ? <Skeleton className="h-48" /> : <WeekChart data={d.week} />}
          </Card>
          <Card className="p-5">
            <h3 className="mb-4 font-semibold">{t("Bugun to'lov turlari")}</h3>
            {d && Object.keys(d.today_by_method).length ? (
              <div className="space-y-3">
                {Object.entries(d.today_by_method).map(([method, sum]) => {
                  const pct = (Number(sum) / Math.max(1, Number(d.today.revenue))) * 100;
                  return (
                    <div key={method}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span>{t(PAYMENT_LABELS[method] ?? method)}</span>
                        <span className="num font-medium">{formatMoney(sum)}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                        <div className="h-full rounded-full bg-brand transition-all duration-700" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-muted">{t("Bugun hali savdo yo'q")}</p>
            )}
            <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <Link to="/stock?low_stock=true" className="rounded-xl bg-surface-2 p-3 hover:bg-brand-soft">
                <AlertTriangle className="h-4 w-4 text-warning" />
                <p className="mt-1 text-lg font-semibold num">{d?.low_stock_count ?? "—"}</p>
                <p className="text-xs text-muted">{t("kam qolgan")}</p>
              </Link>
              <Link to="/expenses" className="rounded-xl bg-surface-2 p-3 hover:bg-brand-soft">
                <Wallet className="h-4 w-4 text-brand" />
                <p className="mt-1 text-lg font-semibold num">{d ? formatNumber(d.today.expenses, 0) : "—"}</p>
                <p className="text-xs text-muted">{t("bugungi xarajat")}</p>
              </Link>
            </div>
          </Card>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {canReports && (
          <Card className="p-5">
            <h3 className="mb-3 font-semibold">{t("Oyning TOP mahsulotlari")}</h3>
            {d?.top_products.length ? (
              <ol className="space-y-2">
                {d.top_products.map((p, i) => (
                  <li key={p.product_id} className="flex items-center gap-3 text-sm">
                    <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-soft text-xs font-semibold text-brand">{i + 1}</span>
                    <span className="flex-1 truncate">{p.name}</span>
                    <span className="num font-medium">{formatNumber(p.revenue, 0)}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted">{t("Ma'lumot yo'q")}</p>
            )}
          </Card>
        )}
        {canReports && (
          <Card className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-semibold">{t("Oxirgi savdolar")}</h3>
              <Link to="/sales" className="text-xs text-brand hover:underline">{t("Tarix →")}</Link>
            </div>
            {d?.recent_sales.length ? (
              <ul className="space-y-2">
                {d.recent_sales.map((s) => (
                  <li key={s.id} className="flex items-center gap-3 text-sm">
                    <Receipt className="h-4 w-4 text-muted" />
                    <span className="flex-1 truncate">#{s.number} {s.customer && <span className="text-muted">· {s.customer}</span>}</span>
                    <span className="text-xs text-muted">{formatDateTime(s.created_at).slice(11)}</span>
                    <span className="num font-medium">{formatNumber(s.total, 0)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">{t("Hali savdo yo'q")}</p>
            )}
          </Card>
        )}
        <RemindersWidget />
        {!canReports && (
          <Card className="p-5 lg:col-span-2">
            <h3 className="font-semibold">{t("Tezkor amallar")}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {can("sales.create") && <Link to="/pos"><Button>{t("Kassa")}</Button></Link>}
              {can("sales.create") && <Link to="/sales"><Button variant="secondary">{t("Mening savdolarim")}</Button></Link>}
              {can("customers.view") && <Link to="/customers"><Button variant="secondary">{t("Mijozlar")}</Button></Link>}
              {can("inventory.view") && <Link to="/stock"><Button variant="secondary">{t("Qoldiqlar")}</Button></Link>}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
