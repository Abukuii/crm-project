import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Download, Printer, Receipt as ReceiptIcon, RotateCcw, Search, Undo2 } from "lucide-react";
import { useState } from "react";

import { t } from "@/i18n";
import { PAYMENT_LABELS, type Page, type Sale, type SalesSummary } from "@/api/types";
import { Drawer, Modal, ReasonDialog } from "@/components/overlay";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Pager, Select, Skeleton, Table, Td, Th } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api, apiDownload } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, formatNumber } from "@/lib/format";
import { formatDateTime, isoDate } from "@/lib/queries";
import { Receipt } from "@/pages/PosPage";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

const SIZE = 30;

const REFUND_LABELS: Record<string, string> = { ...PAYMENT_LABELS, debt: "Qarzdan ayirish" };

interface ReturnBrief {
  id: number;
  number: number;
  refund_method: string;
  total: string;
  reason: string;
  created_by_name: string | null;
  created_at: string;
  status: "posted" | "cancelled";
  cancelled_at: string | null;
  cancel_reason: string;
  cancelled_by_name: string | null;
}

function ReturnModal({ sale, onClose, onDone }: { sale: Sale; onClose: () => void; onDone: (s: Sale) => void }) {
  const left = (l: Sale["lines"][number]) => Number(l.qty) - Number(l.returned_qty);
  const lines = sale.lines.filter((l) => left(l) > 0);
  const [qty, setQty] = useState<Record<number, string>>({});
  const hasCredit = sale.payments.some((p) => p.method === "credit");
  const [method, setMethod] = useState(hasCredit ? "debt" : "cash");
  const [reason, setReason] = useState("");
  const total = lines.reduce((s, l) => s + Number(qty[l.id] || 0) * Number(l.price), 0);
  const invalid = lines.some((l) => Number(qty[l.id] || 0) > left(l) || Number(qty[l.id] || 0) < 0);

  const submit = useMutation({
    mutationFn: () =>
      api<Sale>(`/sales/sales/${sale.id}/returns/`, {
        method: "POST",
        body: {
          items: lines.filter((l) => Number(qty[l.id]) > 0).map((l) => ({ line: l.id, qty: qty[l.id] })),
          refund_method: method,
          reason,
        },
      }),
    onSuccess: (s) => (toast.success(t("Qaytarish saqlandi — tovar omborga qaytdi")), onDone(s)),
    onError: toast.error,
  });

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={t("Qaytarish — savdo #{n}", { n: sale.number })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("Bekor")}</Button>
          <Button variant="danger" loading={submit.isPending} disabled={total <= 0 || invalid} onClick={() => submit.mutate()}>
            <Undo2 className="h-4 w-4" /> {t("Qaytarish")} · {formatMoney(total)}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="overflow-hidden rounded-xl border border-border">
          <Table head={<tr><Th>{t("Mahsulot")}</Th><Th right>{t("Sotilgan")}</Th><Th right>{t("Qaytarish mumkin")}</Th><Th right>{t("Qaytariladi")}</Th></tr>}>
            {lines.map((l) => (
              <tr key={l.id}>
                <Td>{l.product_name}<p className="text-xs text-muted">{formatMoney(l.price)} / {l.unit_short}</p></Td>
                <Td right>{formatNumber(l.qty, 3)} {l.unit_short}</Td>
                <Td right>{formatNumber(left(l), 3)}</Td>
                <Td right>
                  <div className="flex items-center justify-end gap-1">
                    <input
                      className="h-8 w-20 rounded-lg border border-border bg-surface px-2 text-right text-sm num focus:border-brand focus:outline-none"
                      inputMode="decimal"
                      value={qty[l.id] ?? ""}
                      placeholder="0"
                      onChange={(e) => setQty({ ...qty, [l.id]: e.target.value.replace(",", ".") })}
                      aria-label={t("Qaytariladigan miqdor")}
                    />
                    <button className="text-xs text-brand hover:underline" onClick={() => setQty({ ...qty, [l.id]: String(left(l)) })}>
                      {t("hammasi")}
                    </button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label={t("Pul qanday qaytariladi")} value={method} onChange={(e) => setMethod(e.target.value)}>
            {Object.entries(REFUND_LABELS)
              .filter(([k]) => k !== "credit" && (k !== "debt" || hasCredit))
              .map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </Select>
          <Input label={t("Sabab")} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("Masalan: singan, rangi mos kelmadi")} />
        </div>
        {invalid && <p className="text-sm text-danger">{t("Miqdor qaytarish mumkin bo'lganidan ko'p")}</p>}
      </div>
    </Modal>
  );
}

export function SalesPage() {
  const { can, user } = useAuth();
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ date_from: isoDate(), date_to: isoDate(), method: "", status: "", search: "" });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Sale | null>(null);
  const [returning, setReturning] = useState(false);
  const cancelReturn = useMutation({
    mutationFn: ({ ret, reason }: { ret: ReturnBrief; reason: string }) =>
      api<Sale>(`/sales/sales/${selected!.id}/returns/${ret.id}/cancel/`, { method: "POST", body: { reason } }),
    onSuccess: (sale) => {
      toast.success(t("Qaytarish bekor qilindi"));
      setConfirm(null);
      setSelected(sale);
      void qc.invalidateQueries({ queryKey: ["sales"] });
      void qc.invalidateQueries({ queryKey: ["sales-summary"] });
      void qc.invalidateQueries({ queryKey: ["shift"] });
    },
    onError: toast.error,
  });
  const search = useDebounced(filters.search);
  const query = { ...filters, search, page, page_size: SIZE };

  const list = useQuery({
    queryKey: ["sales", query],
    queryFn: () => api<Page<Sale>>("/sales/sales/", { query }),
    placeholderData: keepPreviousData,
  });
  const summary = useQuery({
    queryKey: ["sales-summary", { ...filters, search }],
    queryFn: () => api<SalesSummary>("/sales/sales/summary/", { query: { ...filters, search } }),
  });

  const [confirm, setConfirm] = useState<null | { kind: "sale" } | { kind: "return"; ret: ReturnBrief }>(null);
  const cancel = useMutation({
    mutationFn: ({ sale, reason }: { sale: Sale; reason: string }) =>
      api<Sale>(`/sales/sales/${sale.id}/cancel/`, { method: "POST", body: { reason } }),
    onSuccess: (sale) => {
      toast.success(t("Savdo #{n} bekor qilindi", { n: sale.number }));
      setConfirm(null);
      setSelected(sale);
      void qc.invalidateQueries({ queryKey: ["sales"] });
      void qc.invalidateQueries({ queryKey: ["sales-summary"] });
    },
    onError: toast.error,
  });

  const set = (patch: Partial<typeof filters>) => (setFilters({ ...filters, ...patch }), setPage(1));

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader
        title={t("Savdo tarixi")}
        subtitle={can("reports.view") ? t("Barcha savdolar") : t("Sizning savdolaringiz")}
        actions={
          <Button
            variant="secondary"
            onClick={() => apiDownload("/dataio/sales/export/", `savdolar_${filters.date_from}_${filters.date_to}.xlsx`, filters).catch(toast.error)}
          >
            <Download className="h-4 w-4" /> {t("Excel")}
          </Button>
        }
      />

      <Card className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <Input label={t("Dan")} type="date" value={filters.date_from} onChange={(e) => set({ date_from: e.target.value })} />
        <Input label={t("Gacha")} type="date" value={filters.date_to} onChange={(e) => set({ date_to: e.target.value })} />
        <Select label={t("To'lov turi")} value={filters.method} onChange={(e) => set({ method: e.target.value })}>
          <option value="">{t("Barchasi")}</option>
          {Object.entries(PAYMENT_LABELS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
        </Select>
        <Select label={t("Holat")} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
          <option value="">{t("Barchasi")}</option>
          <option value="posted">{t("O'tkazilgan")}</option>
          <option value="cancelled">{t("Bekor qilingan")}</option>
        </Select>
        <Input label={t("Qidiruv")} placeholder={t("№ yoki mijoz")} icon={<Search className="h-4 w-4" />} value={filters.search} onChange={(e) => set({ search: e.target.value })} />
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: t("Cheklar"), value: summary.data ? formatNumber(summary.data.count) : null },
          { label: t("Savdo summasi"), value: summary.data ? formatMoney(summary.data.total) : null },
          { label: t("Chegirmalar"), value: summary.data ? formatMoney(summary.data.discount) : null },
          ...(summary.data && Number(summary.data.returns) > 0 ? [{ label: t("Qaytarishlar"), value: formatMoney(summary.data.returns) }] : []),
          ...(summary.data?.profit != null ? [{ label: t("Yalpi foyda"), value: formatMoney(summary.data.profit) }] : []),
        ].map((k) => (
          <Card key={k.label} className="p-4">
            <p className="text-sm text-muted">{k.label}</p>
            <p className="mt-1 text-xl font-semibold num">{k.value ?? <Skeleton className="h-7 w-24" />}</p>
          </Card>
        ))}
      </div>
      {summary.data && Object.keys(summary.data.by_method).length > 0 && (
        <div className="flex flex-wrap gap-2 text-sm">
          {Object.entries(summary.data.by_method).map(([m, s]) => (
            <Badge key={m} tone="brand">{t(PAYMENT_LABELS[m] ?? m)}: {formatMoney(s)}</Badge>
          ))}
        </div>
      )}

      <Card className="overflow-hidden">
        {list.isLoading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : !list.data?.results.length ? (
          <EmptyState icon={<ReceiptIcon className="h-6 w-6" />} title={t("Bu davrda savdo yo'q")} />
        ) : (
          <>
            <Table head={<tr><Th>№</Th><Th>{t("Vaqt")}</Th><Th>{t("Mijoz")}</Th><Th>{t("Kassir")}</Th><Th>{t("To'lov")}</Th><Th right>{t("Summa")}</Th></tr>}>
              {list.data.results.map((s) => (
                <tr key={s.id} className="cursor-pointer hover:bg-surface-2/60" onClick={() => setSelected(s)}>
                  <Td className="font-medium num">#{s.number}{s.status === "cancelled" && <Badge tone="danger"> {t("bekor")}</Badge>}</Td>
                  <Td className="text-muted">{formatDateTime(s.created_at)}</Td>
                  <Td>{s.customer_name ?? <span className="text-muted">—</span>}</Td>
                  <Td>{s.cashier_name}</Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      {s.payments.map((p) => <Badge key={p.method} tone={p.method === "credit" ? "warning" : "neutral"}>{t(PAYMENT_LABELS[p.method] ?? p.method)}</Badge>)}
                    </div>
                  </Td>
                  <Td right className={s.status === "cancelled" ? "line-through text-muted" : "font-semibold"}>{formatMoney(s.total)}</Td>
                </tr>
              ))}
            </Table>
            <Pager page={page} count={list.data.count} size={SIZE} onPage={setPage} />
          </>
        )}
      </Card>

      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={t("Savdo #{n}", { n: selected?.number })}
        footer={
          selected && (
            <>
              <Button variant="secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> {t("Chek")}</Button>
              {can("sales.refund") && selected.status === "posted" && selected.lines.some((l) => Number(l.qty) > Number(l.returned_qty)) && (
                <Button variant="secondary" onClick={() => setReturning(true)}>
                  <Undo2 className="h-4 w-4" /> {t("Qaytarish")}
                </Button>
              )}
              {can("sales.refund") && selected.status === "posted" && !(selected.returns as unknown as ReturnBrief[]).some((r) => r.status === "posted") && (
                <Button variant="danger" onClick={() => setConfirm({ kind: "sale" })}>
                  <Ban className="h-4 w-4" /> {t("Bekor qilish")}
                </Button>
              )}
            </>
          )
        }
      >
        {selected && (
          <div className="space-y-4">
            {selected.status === "cancelled" && (
              <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
                {t("Bekor qilingan")}: {formatDateTime(selected.cancelled_at)} {selected.cancel_reason && `— ${selected.cancel_reason}`}
              </p>
            )}
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-muted">{t("Vaqt")}</dt><dd>{formatDateTime(selected.created_at)}</dd></div>
              <div><dt className="text-muted">{t("Kassir")}</dt><dd>{selected.cashier_name}</dd></div>
              <div><dt className="text-muted">{t("Mijoz")}</dt><dd>{selected.customer_name ?? "—"} {selected.customer_phone}</dd></div>
              <div><dt className="text-muted">{t("Ombor")}</dt><dd>{selected.warehouse_name}</dd></div>
              {selected.profit !== undefined && (
                <div><dt className="text-muted">{t("Foyda")}</dt><dd className="font-semibold text-success num">{formatMoney(selected.profit)}</dd></div>
              )}
            </dl>
            {(selected.returns as unknown as ReturnBrief[]).length > 0 && (
              <div className="rounded-xl border border-danger/30 bg-danger/5 p-3 text-sm">
                <p className="mb-2 font-semibold text-danger">{t("Qaytarishlar")}: {formatMoney(selected.returned_total)}</p>
                <ul className="space-y-2">
                  {(selected.returns as unknown as ReturnBrief[]).map((r) => {
                    const cancelled = r.status === "cancelled";
                    return (
                      <li key={r.id} className={cn("flex items-start justify-between gap-2", cancelled && "opacity-60")}>
                        <div className="min-w-0">
                          <p className={cn("text-muted", cancelled && "line-through")}>
                            #{r.number} · {formatDateTime(r.created_at)} · {t(REFUND_LABELS[r.refund_method] ?? r.refund_method)}
                            {r.reason && ` · ${r.reason}`}
                          </p>
                          {cancelled && (
                            <p className="text-xs text-muted">
                              <Badge tone="neutral">{t("bekor qilingan")}</Badge> {formatDateTime(r.cancelled_at)} · {r.cancelled_by_name}
                              {r.cancel_reason && ` · ${r.cancel_reason}`}
                            </p>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className={cn("num font-medium", cancelled && "line-through")}>−{formatMoney(r.total)}</span>
                          {!cancelled && can("sales.refund") && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setConfirm({ kind: "return", ret: r })}
                              title={t("Qaytarishni bekor qilish")}
                            >
                              <RotateCcw className="h-4 w-4" />
                              <span className="hidden sm:inline">{t("Bekor qilish")}</span>
                            </Button>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
            <Card className="p-4"><Receipt sale={selected} tenantName={user?.tenant?.name} /></Card>
          </div>
        )}
      </Drawer>
      <ReasonDialog
        open={!!confirm && !!selected}
        onClose={() => setConfirm(null)}
        loading={cancel.isPending || cancelReturn.isPending}
        title={
          confirm?.kind === "return"
            ? t("Qaytarishni bekor qilish")
            : t("Savdo #{n}", { n: selected?.number })
        }
        message={
          confirm?.kind === "return"
            ? t("Qaytarish #{n} bekor qilinadi: tovar yana ombordan chiqadi, pul kassaga qaytadi.", { n: confirm.ret.number })
            : t("Savdo bekor qilinadi, tovar omborga qaytadi.")
        }
        confirmLabel={t("Bekor qilish")}
        onConfirm={(reason) =>
          confirm?.kind === "return"
            ? cancelReturn.mutate({ ret: confirm.ret, reason })
            : selected && cancel.mutate({ sale: selected, reason })
        }
      />
      {returning && selected && (
        <ReturnModal
          sale={selected}
          onClose={() => setReturning(false)}
          onDone={(s) => {
            setReturning(false);
            setSelected(s);
            void qc.invalidateQueries({ queryKey: ["sales"] });
            void qc.invalidateQueries({ queryKey: ["sales-summary"] });
            void qc.invalidateQueries({ queryKey: ["shift"] });
          }}
        />
      )}
    </div>
  );
}
