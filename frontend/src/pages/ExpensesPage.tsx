import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2, Wallet } from "lucide-react";
import { useState } from "react";

import { t } from "@/i18n";
import type { Expense, Page } from "@/api/types";
import { Modal } from "@/components/overlay";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Pager, Select, Skeleton, Table, Td, Textarea, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { formatDate, isoDate, monthStart, useExpenseCategories } from "@/lib/queries";
import { toast } from "@/stores/toast";

const SIZE = 30;
type Form = { id?: number; name: string; category: number | ""; amount: string; date: string; note: string };

function ExpenseForm({ initial, onClose }: { initial: Form; onClose: () => void }) {
  const qc = useQueryClient();
  const cats = useExpenseCategories();
  const [f, setF] = useState<Form>(initial);
  const save = useMutation({
    mutationFn: () => {
      const body = { name: f.name, category: f.category, amount: f.amount, date: f.date, note: f.note };
      return f.id ? api(`/finance/expenses/${f.id}/`, { method: "PATCH", body }) : api("/finance/expenses/", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(t("Xarajat saqlandi"));
      void qc.invalidateQueries({ queryKey: ["expenses"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
    onError: toast.error,
  });
  return (
    <Modal open onClose={onClose} title={f.id ? t("Xarajatni tahrirlash") : t("Yangi xarajat")}
      footer={<><Button variant="secondary" onClick={onClose}>{t("Bekor")}</Button><Button loading={save.isPending} disabled={!f.name.trim() || !f.category || !Number(f.amount)} onClick={() => save.mutate()}>{t("Saqlash")}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><Input label={t("Nomi")} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoFocus /></div>
        <Select label={t("Kategoriya")} value={f.category} onChange={(e) => setF({ ...f, category: Number(e.target.value) })}>
          <option value="" disabled>{t("Tanlang")}</option>
          {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Input label={t("Summa (so'm)")} type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} />
        <Input label={t("Sana")} type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} />
        <div className="sm:col-span-2"><Textarea label={t("Izoh")} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></div>
      </div>
    </Modal>
  );
}

export function ExpensesPage() {
  const qc = useQueryClient();
  const cats = useExpenseCategories();
  const [filters, setFilters] = useState({ date_from: monthStart(), date_to: isoDate(), category: "" });
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Form | null>(null);
  const query = { ...filters, page, page_size: SIZE };
  const list = useQuery({ queryKey: ["expenses", query], queryFn: () => api<Page<Expense>>("/finance/expenses/", { query }), placeholderData: keepPreviousData });
  const total = useQuery({ queryKey: ["expenses", "total", filters], queryFn: () => api<{ total: string; count: number }>("/finance/expenses/total/", { query: filters }) });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/finance/expenses/${id}/`, { method: "DELETE" }),
    onSuccess: () => (toast.success(t("O'chirildi")), void qc.invalidateQueries({ queryKey: ["expenses"] })),
    onError: toast.error,
  });
  const set = (patch: Partial<typeof filters>) => (setFilters({ ...filters, ...patch }), setPage(1));

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader
        title={t("Xarajatlar")}
        subtitle={total.data && <>Davr bo'yicha: <b className="text-fg num">{formatMoney(total.data.total)}</b> · {total.data.count} ta</>}
        actions={<Button onClick={() => setEditing({ name: "", category: "", amount: "", date: isoDate(), note: "" })}><Plus className="h-4 w-4" /> {t("Xarajat")}</Button>}
      />
      <Card className="grid gap-3 p-4 sm:grid-cols-3">
        <Input label={t("Dan")} type="date" value={filters.date_from} onChange={(e) => set({ date_from: e.target.value })} />
        <Input label={t("Gacha")} type="date" value={filters.date_to} onChange={(e) => set({ date_to: e.target.value })} />
        <Select label={t("Kategoriya")} value={filters.category} onChange={(e) => set({ category: e.target.value })}>
          <option value="">{t("Barchasi")}</option>
          {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </Card>
      <Card className="overflow-hidden">
        {list.isLoading ? <Skeleton className="m-4 h-32" /> : !list.data?.results.length ? (
          <EmptyState icon={<Wallet className="h-6 w-6" />} title={t("Bu davrda xarajat yo'q")} />
        ) : (
          <>
            <Table head={<tr><Th>{t("Sana")}</Th><Th>{t("Nomi")}</Th><Th>{t("Kategoriya")}</Th><Th>{t("Kiritgan")}</Th><Th right>{t("Summa")}</Th><Th /></tr>}>
              {list.data.results.map((x) => (
                <tr key={x.id} className="hover:bg-surface-2/60">
                  <Td>{formatDate(x.date)}</Td>
                  <Td className="font-medium">{x.name}{x.note && <p className="text-xs text-muted">{x.note}</p>}</Td>
                  <Td><Badge tone="brand">{x.category_name}</Badge></Td>
                  <Td className="text-muted">{x.created_by_name}</Td>
                  <Td right className="font-semibold">{formatMoney(x.amount)}</Td>
                  <Td>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" aria-label={t("Tahrirlash")} onClick={() => setEditing({ id: x.id, name: x.name, category: x.category, amount: x.amount, date: x.date ?? isoDate(), note: x.note ?? "" })}><Pencil className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" aria-label={t("O'chirish")} onClick={() => window.confirm(t("Xarajat o'chirilsinmi?")) && remove.mutate(x.id)}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
            <Pager page={page} count={list.data.count} size={SIZE} onPage={setPage} />
          </>
        )}
      </Card>
      {editing && <ExpenseForm initial={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
