import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Download, Printer, Receipt as ReceiptIcon, Search } from "lucide-react";
import { useState } from "react";

import { t } from "@/i18n";
import { PAYMENT_LABELS, type Page, type Sale, type SalesSummary } from "@/api/types";
import { Drawer } from "@/components/overlay";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Pager, Select, Skeleton, Table, Td, Th } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api, apiDownload } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/format";
import { formatDateTime, isoDate } from "@/lib/queries";
import { Receipt } from "@/pages/PosPage";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

const SIZE = 30;

export function SalesPage() {
  const { can, user } = useAuth();
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ date_from: isoDate(), date_to: isoDate(), method: "", status: "", search: "" });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Sale | null>(null);
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

  const cancel = useMutation({
    mutationFn: (sale: Sale) => {
      const reason = window.prompt(t("Savdo #{n} bekor qilinadi, tovar omborga qaytadi. Sabab:", { n: sale.number }));
      if (reason === null) return Promise.reject(new Error("cancelled-by-user"));
      return api<Sale>(`/sales/sales/${sale.id}/cancel/`, { method: "POST", body: { reason } });
    },
    onSuccess: (sale) => {
      toast.success(t("Savdo #{n} bekor qilindi", { n: sale.number }));
      setSelected(sale);
      void qc.invalidateQueries({ queryKey: ["sales"] });
      void qc.invalidateQueries({ queryKey: ["sales-summary"] });
    },
    onError: (e) => (e as Error).message !== "cancelled-by-user" && toast.error(e),
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
              {can("sales.refund") && selected.status === "posted" && (
                <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate(selected)}>
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
            <Card className="p-4"><Receipt sale={selected} tenantName={user?.tenant?.name} /></Card>
          </div>
        )}
      </Drawer>
    </div>
  );
}
