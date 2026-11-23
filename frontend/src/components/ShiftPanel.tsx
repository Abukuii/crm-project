import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowUpFromLine, Clock, FileText, Lock, PlayCircle, Printer } from "lucide-react";
import { useState } from "react";

import { PAYMENT_LABELS, type Shift, type ShiftReport } from "@/api/types";
import { Modal } from "@/components/overlay";
import { Badge, Button, Input } from "@/components/ui";
import { t } from "@/i18n";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import { formatDateTime } from "@/lib/queries";
import { toast } from "@/stores/toast";

const REFUND_LABELS: Record<string, string> = { ...PAYMENT_LABELS, debt: "Qarzdan ayirish" };

/** Joriy smena (yo'q bo'lsa null). */
export function useCurrentShift() {
  return useQuery({
    queryKey: ["shift", "current"],
    queryFn: async () => (await api<Shift | undefined>("/sales/shifts/current/")) ?? null,
  });
}

/** X / Z hisobot — chop etiladigan ko'rinish. */
export function ShiftReportView({ report, final }: { report: ShiftReport; final: boolean }) {
  const row = (label: string, value: string | number | undefined | null, strong = false, tone?: string) => (
    <p className={cn("flex justify-between gap-4", strong && "font-bold", tone)}>
      <span>{label}</span>
      <span className="num">{typeof value === "number" ? value : formatMoney(value)}</span>
    </p>
  );
  const methods = (obj: Record<string, string>, labels = PAYMENT_LABELS) =>
    Object.entries(obj).map(([m, v]) => <div key={m}>{row(`  ${t(labels[m] ?? m)}`, v)}</div>);
  const diff = Number(report.difference ?? 0);
  return (
    <div className="print-area space-y-1 font-mono text-[13px] leading-relaxed">
      <p className="text-center text-sm font-bold">{final ? t("Z-hisobot") : t("X-hisobot")}</p>
      <p className="text-center">
        {t("Smena #{n}", { n: report.shift })} · {report.cashier}
      </p>
      <p className="text-center text-xs">
        {formatDateTime(report.opened_at)} — {report.closed_at ? formatDateTime(report.closed_at) : t("hozir")}
      </p>
      <hr className="my-2 border-dashed border-current" />
      {row(t("Cheklar"), report.sales_count)}
      {row(t("Savdo summasi"), report.sales_total, true)}
      {methods(report.by_method)}
      {Number(report.discount_total) > 0 && row(t("Chegirmalar"), report.discount_total)}
      {report.cancelled_count > 0 && row(t("Bekor qilingan savdolar"), report.cancelled_count)}
      {report.returns_count > 0 && (
        <>
          {row(t("Qaytarishlar"), report.returns_total, false, "text-danger")}
          {methods(report.refunds_by_method, REFUND_LABELS)}
        </>
      )}
      {(report.returns_cancelled_count ?? 0) > 0 && (
        <>
          {row(t("Bekor qilingan qaytarishlar"), report.returns_cancelled_total, false, "text-success")}
          {methods(report.cancelled_refunds_by_method ?? {}, REFUND_LABELS)}
        </>
      )}
      {row(t("Sof savdo"), report.net_revenue, true)}
      {Object.keys(report.debt_payments).length > 0 && (
        <>
          {row(t("Nasiya to'lovlari"), Object.values(report.debt_payments).reduce((a, b) => a + Number(b), 0))}
          {methods(report.debt_payments)}
        </>
      )}
      <hr className="my-2 border-dashed border-current" />
      {row(t("Boshlang'ich naqd"), report.opening_cash)}
      {Number(report.cash_in) > 0 && row(t("Kassaga kiritildi"), report.cash_in)}
      {Number(report.cash_out) > 0 && row(t("Kassadan olindi"), report.cash_out)}
      {row(t("Kassada bo'lishi kerak"), report.expected_cash, true)}
      {report.counted_cash != null && (
        <>
          {row(t("Sanalgan naqd"), report.counted_cash, true)}
          {row(t("Farq"), report.difference, true, diff < 0 ? "text-danger" : diff > 0 ? "text-success" : "")}
        </>
      )}
    </div>
  );
}

/** Kassa sahifasidagi smena paneli. */
export function ShiftPanel({ warehouseId }: { warehouseId: number | null }) {
  const qc = useQueryClient();
  const { data: shift, isLoading } = useCurrentShift();
  const [dialog, setDialog] = useState<null | "open" | "in" | "out" | "x" | "close">(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [zReport, setZReport] = useState<ShiftReport | null>(null);

  const report = useQuery({
    queryKey: ["shift", shift?.id, "report"],
    queryFn: () => api<ShiftReport>(`/sales/shifts/${shift!.id}/report/`),
    enabled: !!shift && (dialog === "x" || dialog === "close"),
  });

  const reset = () => (setDialog(null), setAmount(""), setNote(""));
  const refresh = () => void qc.invalidateQueries({ queryKey: ["shift"] });

  const openShift = useMutation({
    mutationFn: () =>
      api<Shift>("/sales/shifts/open/", { method: "POST", body: { warehouse: warehouseId, opening_cash: amount || "0", note } }),
    onSuccess: (s) => (toast.success(t("Smena #{n} ochildi", { n: s.number })), reset(), refresh()),
    onError: toast.error,
  });
  const move = useMutation({
    mutationFn: (kind: "in" | "out") =>
      api(`/sales/shifts/${shift!.id}/cash/`, { method: "POST", body: { kind, amount, note } }),
    onSuccess: () => (toast.success(t("Saqlandi")), reset(), refresh()),
    onError: toast.error,
  });
  const close = useMutation({
    mutationFn: () =>
      api<ShiftReport>(`/sales/shifts/${shift!.id}/close/`, { method: "POST", body: { counted_cash: amount || "0", note } }),
    onSuccess: (z) => {
      reset();
      setZReport(z);
      refresh();
      void qc.invalidateQueries({ queryKey: ["shifts"] });
    },
    onError: toast.error,
  });

  if (isLoading) return null;

  return (
    <>
      {shift ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm">
          <Badge tone="success">
            <Clock className="mr-1 h-3 w-3" />
            {t("Smena #{n}", { n: shift.number })}
          </Badge>
          <span className="text-xs text-muted">{formatDateTime(shift.opened_at)}</span>
          <div className="ml-auto flex flex-wrap gap-1">
            <Button variant="ghost" size="sm" onClick={() => setDialog("in")} title={t("Kassaga naqd kiritish")}>
              <ArrowDownToLine className="h-4 w-4" />
              <span className="hidden xl:inline">{t("Kiritish")}</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDialog("out")} title={t("Kassadan naqd olish")}>
              <ArrowUpFromLine className="h-4 w-4" />
              <span className="hidden xl:inline">{t("Olish")}</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDialog("x")}>
              <FileText className="h-4 w-4" /> X
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setDialog("close")}>
              <Lock className="h-4 w-4" /> {t("Smenani yopish")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-xl border border-warning/40 bg-warning/5 px-3 py-2 text-sm">
          <span className="flex-1 text-warning">{t("Smena ochilmagan")}</span>
          <Button size="sm" disabled={warehouseId === null} onClick={() => setDialog("open")}>
            <PlayCircle className="h-4 w-4" /> {t("Smena ochish")}
          </Button>
        </div>
      )}

      <Modal
        open={dialog === "open"}
        onClose={reset}
        size="sm"
        title={t("Smena ochish")}
        footer={
          <>
            <Button variant="secondary" onClick={reset}>{t("Bekor")}</Button>
            <Button loading={openShift.isPending} onClick={() => openShift.mutate()}>{t("Ochish")}</Button>
          </>
        }
      >
        <Input label={t("Kassadagi boshlang'ich naqd (so'm)")} type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
      </Modal>

      <Modal
        open={dialog === "in" || dialog === "out"}
        onClose={reset}
        size="sm"
        title={dialog === "in" ? t("Kassaga naqd kiritish") : t("Kassadan naqd olish")}
        footer={
          <>
            <Button variant="secondary" onClick={reset}>{t("Bekor")}</Button>
            <Button loading={move.isPending} disabled={!Number(amount)} onClick={() => move.mutate(dialog as "in" | "out")}>
              {t("Saqlash")}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Input label={t("Summa (so'm)")} type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          <Input
            label={t("Izoh")}
            placeholder={dialog === "out" ? t("Masalan: inkassatsiya, mayda xarajat") : t("Masalan: maydalash uchun")}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
      </Modal>

      <Modal
        open={dialog === "x"}
        onClose={reset}
        size="sm"
        title={t("X-hisobot (joriy holat)")}
        footer={<Button variant="secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> {t("Chop etish")}</Button>}
      >
        {report.data ? <ShiftReportView report={report.data} final={false} /> : <div className="h-40 animate-pulse rounded-lg bg-surface-2" />}
      </Modal>

      <Modal
        open={dialog === "close"}
        onClose={reset}
        size="sm"
        title={t("Smenani yopish")}
        footer={
          <>
            <Button variant="secondary" onClick={reset}>{t("Bekor")}</Button>
            <Button loading={close.isPending} disabled={amount === ""} onClick={() => close.mutate()}>
              <Lock className="h-4 w-4" /> {t("Yopish va Z-hisobot")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {report.data && (
            <div className="rounded-xl bg-surface-2 p-4 text-center">
              <p className="text-sm text-muted">{t("Kassada bo'lishi kerak")}</p>
              <p className="text-2xl font-bold num">{formatMoney(report.data.expected_cash)}</p>
            </div>
          )}
          <Input label={t("Sanalgan naqd (so'm)")} type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          {report.data && amount !== "" && (
            <p className={cn("text-center text-sm font-medium",
              Number(amount) === Number(report.data.expected_cash) ? "text-success" : "text-warning")}>
              {t("Farq")}: {formatMoney(Number(amount) - Number(report.data.expected_cash))}
            </p>
          )}
          <Input label={t("Izoh")} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </Modal>

      <Modal
        open={!!zReport}
        onClose={() => setZReport(null)}
        size="sm"
        title={t("Smena yopildi")}
        footer={
          <>
            <Button variant="secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> {t("Chop etish")}</Button>
            <Button onClick={() => setZReport(null)}>{t("Yopish")}</Button>
          </>
        }
      >
        {zReport && <ShiftReportView report={zReport} final />}
      </Modal>
    </>
  );
}
