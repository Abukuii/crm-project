import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HandCoins, Pencil, Plus, Truck } from "lucide-react";
import { useState } from "react";

import { t } from "@/i18n";
import type { Page, Statement, Supplier } from "@/api/types";
import { Drawer, Modal } from "@/components/overlay";
import { Button, Card, EmptyState, Input, PageHeader, Select, Skeleton, Table, Td, Textarea, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { formatDate, monthStart, isoDate } from "@/lib/queries";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

type Form = Partial<Supplier> & { name: string };

function SupplierForm({ initial, onClose }: { initial: Form; onClose: () => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState<Form>(initial);
  const save = useMutation({
    mutationFn: () => {
      const body = { name: f.name, phone: f.phone ?? "", inn: f.inn ?? "", currency: f.currency ?? "UZS", note: f.note ?? "" };
      return f.id ? api(`/purchasing/suppliers/${f.id}/`, { method: "PATCH", body }) : api("/purchasing/suppliers/", { method: "POST", body });
    },
    onSuccess: () => (toast.success(t("Saqlandi")), void qc.invalidateQueries({ queryKey: ["suppliers"] }), onClose()),
    onError: toast.error,
  });
  return (
    <Modal open onClose={onClose} title={f.id ? t("Yetkazib beruvchi") : t("Yangi yetkazib beruvchi")}
      footer={<><Button variant="secondary" onClick={onClose}>{t("Bekor")}</Button><Button loading={save.isPending} disabled={!f.name.trim()} onClick={() => save.mutate()}>{t("Saqlash")}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><Input label={t("Nomi")} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoFocus /></div>
        <Input label={t("Telefon")} value={f.phone ?? ""} onChange={(e) => setF({ ...f, phone: e.target.value })} />
        <Input label={t("INN")} value={f.inn ?? ""} onChange={(e) => setF({ ...f, inn: e.target.value })} />
        <Select label={t("Hisob valyutasi")} value={f.currency ?? "UZS"} onChange={(e) => setF({ ...f, currency: e.target.value as "UZS" | "USD" })}>
          <option value="UZS">{t("So'm")}</option><option value="USD">{t("Dollar")}</option>
        </Select>
        <div className="sm:col-span-2"><Textarea label={t("Izoh")} value={f.note ?? ""} onChange={(e) => setF({ ...f, note: e.target.value })} /></div>
      </div>
    </Modal>
  );
}

function SupplierDrawer({ supplier, onClose }: { supplier: Supplier; onClose: () => void }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [range, setRange] = useState({ date_from: monthStart(), date_to: isoDate() });
  const [amount, setAmount] = useState("");
  const st = useQuery({
    queryKey: ["suppliers", supplier.id, "statement", range],
    queryFn: () => api<Statement>(`/purchasing/suppliers/${supplier.id}/statement/`, { query: range }),
  });
  const pay = useMutation({
    mutationFn: () => api(`/purchasing/suppliers/${supplier.id}/payments/`, { method: "POST", body: { amount } }),
    onSuccess: () => (toast.success(t("To'lov yozildi")), setAmount(""), void qc.invalidateQueries({ queryKey: ["suppliers"] })),
    onError: toast.error,
  });
  const cur = supplier.currency;
  return (
    <Drawer open onClose={onClose} title={supplier.name}>
      <div className="space-y-4">
        <Card className="p-4">
          <p className="text-sm text-muted">{t("Biz qarzdormiz")}</p>
          <p className={cn("text-2xl font-bold num", Number(supplier.balance) > 0 ? "text-danger" : "text-success")}>
            {formatNumber(supplier.balance, 2)} {cur}
          </p>
        </Card>
        {can("finance.manage") && (
          <div className="flex gap-2">
            <Input type="number" placeholder={t("To'lov summasi ({cur})", { cur })} value={amount} onChange={(e) => setAmount(e.target.value)} aria-label={t("Summa")} />
            <Button loading={pay.isPending} disabled={!Number(amount)} onClick={() => pay.mutate()}><HandCoins className="h-4 w-4" /> {t("To'lash")}</Button>
          </div>
        )}
        <div>
          <h3 className="mb-2 font-semibold">{t("Akt sverka")}</h3>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <Input type="date" aria-label={t("Dan")} value={range.date_from} onChange={(e) => setRange({ ...range, date_from: e.target.value })} />
            <Input type="date" aria-label={t("Gacha")} value={range.date_to} onChange={(e) => setRange({ ...range, date_to: e.target.value })} />
          </div>
          {st.isLoading || !st.data ? <Skeleton className="h-32" /> : (
            <div className="overflow-hidden rounded-xl border border-border">
              <Table head={<tr><Th>{t("Sana")}</Th><Th>{t("Hujjat")}</Th><Th right>{t("Kirim")}</Th><Th right>{t("To'lov")}</Th><Th right>{t("Qoldiq")}</Th></tr>}>
                <tr className="bg-surface-2/50"><Td className="text-muted" >Davr boshi</Td><Td /><Td /><Td /><Td right className="font-medium">{formatNumber(st.data.opening, 2)}</Td></tr>
                {st.data.rows.map((r, i) => (
                  <tr key={i}>
                    <Td>{formatDate(r.date)}</Td><Td>{r.ref}</Td>
                    <Td right>{Number(r.debit) ? formatNumber(r.debit, 2) : ""}</Td>
                    <Td right className="text-success">{Number(r.credit) ? formatNumber(r.credit, 2) : ""}</Td>
                    <Td right>{formatNumber(r.balance, 2)}</Td>
                  </tr>
                ))}
                <tr className="bg-surface-2/50 font-semibold"><Td>{t("Davr oxiri")}</Td><Td /><Td right>{formatNumber(st.data.debit_total, 2)}</Td><Td right>{formatNumber(st.data.credit_total, 2)}</Td><Td right>{formatNumber(st.data.closing, 2)}</Td></tr>
              </Table>
            </div>
          )}
        </div>
      </div>
    </Drawer>
  );
}

export function SuppliersPage() {
  const { can } = useAuth();
  const [editing, setEditing] = useState<Form | null>(null);
  const [opened, setOpened] = useState<Supplier | null>(null);
  const list = useQuery({
    queryKey: ["suppliers", "list"],
    queryFn: () => api<Page<Supplier>>("/purchasing/suppliers/", { query: { page_size: 500, is_archived: false } }),
  });
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader title={t("Yetkazib beruvchilar")} actions={can("inventory.manage") && <Button onClick={() => setEditing({ name: "" })}><Plus className="h-4 w-4" /> {t("Qo'shish")}</Button>} />
      <Card className="overflow-hidden">
        {list.isLoading ? <Skeleton className="m-4 h-32" /> : !list.data?.results.length ? (
          <EmptyState icon={<Truck className="h-6 w-6" />} title={t("Yetkazib beruvchi yo'q")} />
        ) : (
          <Table head={<tr><Th>{t("Nomi")}</Th><Th>{t("Telefon")}</Th><Th>{t("Valyuta")}</Th><Th right>{t("Qarzimiz")}</Th><Th /></tr>}>
            {list.data.results.map((s) => (
              <tr key={s.id} className="cursor-pointer hover:bg-surface-2/60" onClick={() => setOpened(s)}>
                <Td className="font-medium">{s.name}</Td>
                <Td className="text-muted">{s.phone || "—"}</Td>
                <Td>{s.currency}</Td>
                <Td right className={Number(s.balance) > 0 ? "font-semibold text-danger" : "text-muted"}>{formatNumber(s.balance, 2)}</Td>
                <Td>{can("inventory.manage") && <button onClick={(e) => (e.stopPropagation(), setEditing(s))} className="text-muted hover:text-brand" aria-label={t("Tahrirlash")}><Pencil className="h-4 w-4" /></button>}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing && <SupplierForm initial={editing} onClose={() => setEditing(null)} />}
      {opened && <SupplierDrawer supplier={opened} onClose={() => setOpened(null)} />}
    </div>
  );
}
