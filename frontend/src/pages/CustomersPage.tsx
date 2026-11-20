import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HandCoins, Pencil, Plus, Search, Users } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import type { Customer, CustomerPayment, Page, Receivable } from "@/api/types";
import { Drawer, Modal } from "@/components/overlay";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Pager, Select, Skeleton, Table, Td, Textarea, Th } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import { formatDate, formatDateTime, usePriceTypes } from "@/lib/queries";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

const SIZE = 30;
const KINDS: Record<string, string> = { person: "Jismoniy", master: "Usta", company: "Yuridik" };

type Form = Partial<Customer> & { name: string };

function CustomerForm({ initial, onClose }: { initial: Form | null; onClose: () => void }) {
  const qc = useQueryClient();
  const priceTypes = usePriceTypes();
  const [form, setForm] = useState<Form>(initial ?? { name: "" });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name, phone: form.phone ?? "", address: form.address ?? "", kind: form.kind ?? "person",
        price_type: form.price_type ?? null, credit_limit: form.credit_limit || null,
        payment_days: Number(form.payment_days ?? 0), note: form.note ?? "", inn: form.inn ?? "",
      };
      return form.id
        ? api<Customer>(`/sales/customers/${form.id}/`, { method: "PATCH", body })
        : api<Customer>("/sales/customers/", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success("Saqlandi");
      void qc.invalidateQueries({ queryKey: ["customers"] });
      onClose();
    },
    onError: toast.error,
  });
  const set = (patch: Partial<Form>) => setForm({ ...form, ...patch });
  return (
    <Modal
      open
      onClose={onClose}
      title={form.id ? "Mijozni tahrirlash" : "Yangi mijoz"}
      footer={<><Button variant="secondary" onClick={onClose}>Bekor</Button><Button loading={save.isPending} disabled={!form.name.trim()} onClick={() => save.mutate()}>Saqlash</Button></>}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><Input label="F.I.Sh. / nomi" value={form.name} onChange={(e) => set({ name: e.target.value })} autoFocus /></div>
        <Input label="Telefon" inputMode="tel" value={form.phone ?? ""} onChange={(e) => set({ phone: e.target.value })} />
        <Select label="Turi" value={form.kind ?? "person"} onChange={(e) => set({ kind: e.target.value as Customer["kind"] })}>
          {Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <div className="sm:col-span-2"><Input label="Manzil" value={form.address ?? ""} onChange={(e) => set({ address: e.target.value })} /></div>
        <Select label="Narx turi" value={form.price_type ?? ""} onChange={(e) => set({ price_type: e.target.value ? Number(e.target.value) : null })}>
          <option value="">Standart</option>
          {priceTypes.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Select>
        <Input label="Kredit limiti (bo'sh — cheksiz)" type="number" value={form.credit_limit ?? ""} onChange={(e) => set({ credit_limit: e.target.value || null })} />
        <Input label="Nasiya muddati (kun)" type="number" min={0} value={form.payment_days ?? 0} onChange={(e) => set({ payment_days: Number(e.target.value) })} />
        <Input label="INN" value={form.inn ?? ""} onChange={(e) => set({ inn: e.target.value })} />
        <div className="sm:col-span-2"><Textarea label="Izoh" value={form.note ?? ""} onChange={(e) => set({ note: e.target.value })} /></div>
      </div>
    </Modal>
  );
}

function CustomerDrawer({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const receivables = useQuery({
    queryKey: ["customers", customer.id, "receivables"],
    queryFn: () => api<Receivable[]>(`/sales/customers/${customer.id}/receivables/`),
  });
  const payments = useQuery({
    queryKey: ["customers", customer.id, "payments"],
    queryFn: () => api<Page<CustomerPayment>>(`/sales/customers/${customer.id}/payments/`),
  });
  const fresh = useQuery({
    queryKey: ["customers", customer.id],
    queryFn: () => api<Customer>(`/sales/customers/${customer.id}/`),
    initialData: customer,
  });
  const debt = Number(fresh.data.debt ?? 0);

  const pay = useMutation({
    mutationFn: (sum: string) => api(`/sales/customers/${customer.id}/payments/`, { method: "POST", body: { amount: sum, method } }),
    onSuccess: () => {
      toast.success("To'lov qabul qilindi");
      setAmount("");
      void qc.invalidateQueries({ queryKey: ["customers"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: toast.error,
  });

  return (
    <Drawer open onClose={onClose} title={fresh.data.name}>
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <Card className="p-4">
            <p className="text-sm text-muted">Joriy qarz</p>
            <p className={cn("text-2xl font-bold num", debt > 0 ? "text-danger" : "text-success")}>{formatMoney(debt)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted">Muddati o'tgan</p>
            <p className="text-2xl font-bold num text-warning">{formatMoney(fresh.data.overdue_debt)}</p>
          </Card>
        </div>
        <p className="text-sm text-muted">
          {fresh.data.phone || "telefon yo'q"} · {KINDS[fresh.data.kind ?? "person"]}
          {fresh.data.credit_limit && <> · limit {formatMoney(fresh.data.credit_limit)}</>}
        </p>

        {can("debts.collect") && debt > 0 && (
          <Card className="space-y-3 p-4">
            <h3 className="flex items-center gap-2 font-semibold"><HandCoins className="h-4 w-4 text-brand" /> To'lov qabul qilish</h3>
            <div className="grid grid-cols-[1fr_140px] gap-2">
              <Input type="number" inputMode="decimal" placeholder="Summa" value={amount} onChange={(e) => setAmount(e.target.value)} aria-label="Summa" />
              <Select value={method} onChange={(e) => setMethod(e.target.value)} aria-label="To'lov turi">
                <option value="cash">Naqd</option><option value="card">Karta</option><option value="transfer">O'tkazma</option>
              </Select>
            </div>
            <div className="flex gap-2">
              <Button className="flex-1" loading={pay.isPending} disabled={!Number(amount) || Number(amount) > debt} onClick={() => pay.mutate(amount)}>Qisman to'lash</Button>
              <Button variant="secondary" className="flex-1" loading={pay.isPending} onClick={() => window.confirm(`${formatMoney(debt)} to'liq qabul qilinsinmi?`) && pay.mutate(String(debt))}>
                To'liq to'lash
              </Button>
            </div>
          </Card>
        )}

        <div>
          <h3 className="mb-2 font-semibold">Nasiya savdolar</h3>
          {receivables.isLoading ? <Skeleton className="h-24" /> : !receivables.data?.length ? (
            <p className="text-sm text-muted">Nasiya yo'q</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {receivables.data.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                  <div>
                    <p className="font-medium">Savdo #{r.sale_number} <span className="text-muted">· {formatDate(r.sale_date)}</span></p>
                    <p className="text-xs text-muted">Muddat: {formatDate(r.due_date)} {r.is_overdue && <Badge tone="danger">o'tgan</Badge>}</p>
                  </div>
                  <div className="text-right">
                    <p className="num font-semibold">{formatMoney(r.remaining)}</p>
                    <p className="text-xs text-muted num">{formatMoney(r.paid)} / {formatMoney(r.amount)}</p>
                  </div>
                  <Badge tone={r.status === "open" ? "warning" : r.status === "closed" ? "success" : "neutral"}>
                    {r.status === "open" ? "ochiq" : r.status === "closed" ? "yopilgan" : "bekor"}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="mb-2 font-semibold">To'lovlar tarixi</h3>
          {!payments.data?.results.length ? <p className="text-sm text-muted">To'lov yo'q</p> : (
            <ul className="space-y-1 text-sm">
              {payments.data.results.map((p) => (
                <li key={p.id} className="flex justify-between">
                  <span className="text-muted">{formatDateTime(p.created_at)} · {p.created_by_name}</span>
                  <span className="num font-medium text-success">+{formatMoney(p.amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Drawer>
  );
}

export function CustomersPage() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get("has_debt") === "true" ? "debt" : params.get("overdue") === "true" ? "overdue" : "all";
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Form | null>(null);
  const [opened, setOpened] = useState<Customer | null>(null);
  const debounced = useDebounced(search);
  const query = {
    search: debounced, page, page_size: SIZE, is_archived: false,
    has_debt: tab === "debt" ? true : undefined, overdue: tab === "overdue" ? true : undefined,
    ordering: tab === "all" ? "name" : "-debt",
  };
  const list = useQuery({
    queryKey: ["customers", query],
    queryFn: () => api<Page<Customer>>("/sales/customers/", { query }),
    placeholderData: keepPreviousData,
  });
  const setTab = (t: string) => {
    setPage(1);
    setParams(t === "debt" ? { has_debt: "true" } : t === "overdue" ? { overdue: "true" } : {});
  };

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader
        title="Mijozlar va qarzlar"
        subtitle={list.data ? `${list.data.count} ta` : undefined}
        actions={can("customers.manage") && <Button onClick={() => setEditing({ name: "" })}><Plus className="h-4 w-4" /> Mijoz</Button>}
      />
      <div className="flex flex-wrap items-center gap-2">
        {[["all", "Barchasi"], ["debt", "Qarzdorlar"], ["overdue", "Muddati o'tgan"]].map(([k, v]) => (
          <button
            key={k}
            onClick={() => setTab(k!)}
            className={cn("rounded-full px-4 py-1.5 text-sm font-medium transition-colors", tab === k ? "bg-brand text-on-brand" : "bg-surface-2 text-muted hover:text-fg")}
          >
            {v}
          </button>
        ))}
        <div className="ml-auto w-full sm:w-72">
          <Input placeholder="Ism yoki telefon" icon={<Search className="h-4 w-4" />} value={search} onChange={(e) => (setSearch(e.target.value), setPage(1))} aria-label="Qidiruv" />
        </div>
      </div>
      <Card className="overflow-hidden">
        {list.isLoading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : !list.data?.results.length ? (
          <EmptyState icon={<Users className="h-6 w-6" />} title={tab === "all" ? "Mijoz yo'q" : "Qarzdor yo'q"} />
        ) : (
          <>
            <Table head={<tr><Th>Mijoz</Th><Th>Telefon</Th><Th>Turi</Th><Th right>Qarz</Th><Th right>Muddati o'tgan</Th><Th /></tr>}>
              {list.data.results.map((c) => (
                <tr key={c.id} className="cursor-pointer hover:bg-surface-2/60" onClick={() => setOpened(c)}>
                  <Td className="font-medium">{c.name}</Td>
                  <Td className="text-muted">{c.phone || "—"}</Td>
                  <Td><Badge>{KINDS[c.kind ?? "person"]}</Badge></Td>
                  <Td right className={Number(c.debt) > 0 ? "font-semibold text-danger" : "text-muted"}>{formatMoney(c.debt)}</Td>
                  <Td right className={Number(c.overdue_debt) > 0 ? "text-warning" : "text-muted"}>{formatMoney(c.overdue_debt)}</Td>
                  <Td>
                    {can("customers.manage") && (
                      <button onClick={(e) => (e.stopPropagation(), setEditing(c))} className="text-muted hover:text-brand" aria-label="Tahrirlash">
                        <Pencil className="h-4 w-4" />
                      </button>
                    )}
                  </Td>
                </tr>
              ))}
            </Table>
            <Pager page={page} count={list.data.count} size={SIZE} onPage={setPage} />
          </>
        )}
      </Card>
      {editing && <CustomerForm initial={editing} onClose={() => setEditing(null)} />}
      {opened && <CustomerDrawer customer={opened} onClose={() => setOpened(null)} />}
    </div>
  );
}
