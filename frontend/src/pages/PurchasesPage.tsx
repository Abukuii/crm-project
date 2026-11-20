import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CheckCircle2, ClipboardList, Plus, Save, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import type { Page, Product, Purchase, Supplier } from "@/api/types";
import { Drawer } from "@/components/overlay";
import { ProductPicker } from "@/components/ProductPicker";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Pager, Select, Skeleton, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/format";
import { formatDate, isoDate, useWarehouses } from "@/lib/queries";
import { toast } from "@/stores/toast";

const SIZE = 30;
const STATUS: Record<string, { label: string; tone: "neutral" | "success" | "danger" }> = {
  draft: { label: "Qoralama", tone: "neutral" },
  posted: { label: "O'tkazilgan", tone: "success" },
  cancelled: { label: "Bekor", tone: "danger" },
};

interface Line {
  product: number;
  product_name: string;
  units: { id: number; short: string }[];
  unit: number;
  qty: string;
  price: string;
}

function productUnits(p: Product) {
  return [{ id: p.base_unit, short: p.base_unit_short }, ...(p.units ?? []).map((u) => ({ id: u.unit, short: u.unit_short }))];
}

function PurchaseEditor({ purchase, onClose }: { purchase: Purchase | null; onClose: () => void }) {
  const qc = useQueryClient();
  const warehouses = useWarehouses();
  const suppliers = useQuery({
    queryKey: ["suppliers", "all"],
    queryFn: () => api<Page<Supplier>>("/purchasing/suppliers/", { query: { page_size: 500, is_archived: false } }),
  });
  const editable = !purchase || purchase.status === "draft";
  const [head, setHead] = useState({
    supplier: purchase?.supplier ?? null,
    warehouse: purchase?.warehouse ?? null,
    date: purchase?.date ?? isoDate(),
    currency: purchase?.currency ?? "UZS",
    extra_costs: purchase?.extra_costs ?? "0",
    note: purchase?.note ?? "",
  });
  const [lines, setLines] = useState<Line[]>(
    () =>
      purchase?.lines?.map((l) => ({
        product: l.product, product_name: l.product_name, units: [{ id: l.unit, short: l.unit_short }],
        unit: l.unit, qty: l.qty, price: l.price,
      })) ?? [],
  );
  const warehouseId = head.warehouse ?? warehouses.data?.[0]?.id ?? null;
  const subtotal = useMemo(() => lines.reduce((s, l) => s + Number(l.qty || 0) * Number(l.price || 0), 0), [lines]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["purchases"] });
    void qc.invalidateQueries({ queryKey: ["balances"] });
    void qc.invalidateQueries({ queryKey: ["suppliers"] });
  };

  const save = useMutation({
    mutationFn: async (andPost: boolean) => {
      const body = { ...head, warehouse: warehouseId, lines: lines.map(({ product, unit, qty, price }) => ({ product, unit, qty, price })) };
      const doc = purchase
        ? await api<Purchase>(`/purchasing/purchases/${purchase.id}/`, { method: "PATCH", body })
        : await api<Purchase>("/purchasing/purchases/", { method: "POST", body });
      return andPost ? api<Purchase>(`/purchasing/purchases/${doc.id}/post/`, { method: "POST" }) : doc;
    },
    onSuccess: (doc) => {
      toast.success(doc.status === "posted" ? `Kirim #${doc.number} o'tkazildi — qoldiq oshdi` : `Kirim #${doc.number} saqlandi`);
      invalidate();
      onClose();
    },
    onError: toast.error,
  });
  const cancel = useMutation({
    mutationFn: () => api<Purchase>(`/purchasing/purchases/${purchase!.id}/cancel/`, { method: "POST" }),
    onSuccess: () => (toast.success("Kirim bekor qilindi"), invalidate(), onClose()),
    onError: toast.error,
  });
  const remove = useMutation({
    mutationFn: () => api(`/purchasing/purchases/${purchase!.id}/`, { method: "DELETE" }),
    onSuccess: () => (toast.success("Qoralama o'chirildi"), invalidate(), onClose()),
    onError: toast.error,
  });

  const addProduct = (p: Product) => {
    const units = productUnits(p);
    setLines((ls) => [...ls, { product: p.id, product_name: p.name, units, unit: units[0]!.id, qty: "1", price: "" }]);
  };

  return (
    <Drawer
      open
      onClose={onClose}
      title={purchase ? `Kirim #${purchase.number}` : "Yangi kirim"}
      footer={
        editable ? (
          <>
            {purchase && <Button variant="ghost" onClick={() => window.confirm("Qoralama o'chirilsinmi?") && remove.mutate()}><Trash2 className="h-4 w-4" /></Button>}
            <Button variant="secondary" loading={save.isPending} disabled={!lines.length} onClick={() => save.mutate(false)}><Save className="h-4 w-4" /> Qoralama</Button>
            <Button loading={save.isPending} disabled={!lines.length || lines.some((l) => !Number(l.qty) || l.price === "")} onClick={() => save.mutate(true)}>
              <CheckCircle2 className="h-4 w-4" /> O'tkazish
            </Button>
          </>
        ) : purchase?.status === "posted" ? (
          <Button variant="danger" loading={cancel.isPending} onClick={() => window.confirm("Kirim bekor qilinadi, tovar ombordan chiqariladi. Davom etilsinmi?") && cancel.mutate()}>
            <Ban className="h-4 w-4" /> Bekor qilish
          </Button>
        ) : null
      }
    >
      <div className="space-y-4">
        {purchase && <Badge tone={STATUS[purchase.status!]?.tone}>{STATUS[purchase.status!]?.label}</Badge>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Yetkazib beruvchi" disabled={!editable} value={head.supplier ?? ""} onChange={(e) => {
            const s = suppliers.data?.results.find((x) => x.id === Number(e.target.value));
            setHead({ ...head, supplier: s?.id ?? null, currency: s?.currency ?? head.currency });
          }}>
            <option value="">— (yetkazib beruvchisiz)</option>
            {suppliers.data?.results.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.currency})</option>)}
          </Select>
          <Select label="Ombor" disabled={!editable} value={warehouseId ?? ""} onChange={(e) => setHead({ ...head, warehouse: Number(e.target.value) })}>
            {warehouses.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
          <Input label="Sana" type="date" disabled={!editable} value={head.date} onChange={(e) => setHead({ ...head, date: e.target.value })} />
          <Select label="Valyuta" disabled={!editable || !!head.supplier} value={head.currency} onChange={(e) => setHead({ ...head, currency: e.target.value as "UZS" | "USD" })}>
            <option value="UZS">So'm</option><option value="USD">Dollar</option>
          </Select>
          <Input label="Qo'shimcha xarajat (so'm): transport, yuklash" type="number" disabled={!editable} value={head.extra_costs} onChange={(e) => setHead({ ...head, extra_costs: e.target.value })} />
          <Input label="Izoh" disabled={!editable} value={head.note} onChange={(e) => setHead({ ...head, note: e.target.value })} />
        </div>

        {editable && <ProductPicker onPick={addProduct} />}

        {lines.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted">Tovar qo'shing</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border">
            {lines.map((l, i) => {
              const posted = purchase?.lines?.[i];
              return (
                <li key={i} className="space-y-2 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{l.product_name}</span>
                    {editable && (
                      <button className="text-muted hover:text-danger" onClick={() => setLines(lines.filter((_, j) => j !== i))} aria-label="O'chirish">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-[90px_100px_1fr] gap-2">
                    <Input aria-label="Miqdor" type="number" disabled={!editable} value={l.qty} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, qty: e.target.value } : x)))} />
                    <Select aria-label="Birlik" disabled={!editable} value={l.unit} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, unit: Number(e.target.value) } : x)))}>
                      {l.units.map((u) => <option key={u.id} value={u.id}>{u.short}</option>)}
                    </Select>
                    <Input aria-label="Xarid narxi" placeholder={`Narx (${head.currency})`} type="number" step="any" disabled={!editable} value={l.price} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, price: e.target.value } : x)))} />
                  </div>
                  <div className="flex justify-between text-xs text-muted">
                    <span>{posted?.unit_cost && <>Tannarx (so'm, asosiy birlik): {formatNumber(posted.unit_cost, 2)}</>}</span>
                    <span className="text-sm font-semibold text-fg num">{formatNumber(Number(l.qty || 0) * Number(l.price || 0), 2)} {head.currency}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <div className="flex items-end justify-between rounded-xl bg-surface-2 p-4">
          <span className="text-sm text-muted">Tovarlar jami</span>
          <span className="text-2xl font-bold num">{formatNumber(subtotal, 2)} {head.currency}</span>
        </div>
        {purchase?.status === "posted" && (
          <p className="text-sm text-muted">So'mda (xarajatlar bilan): <b className="text-fg">{formatMoney(purchase.total_uzs)}</b> · kurs {purchase.rate}</p>
        )}
      </div>
    </Drawer>
  );
}

export function PurchasesPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [opened, setOpened] = useState<Purchase | "new" | null>(null);
  const query = { status, page, page_size: SIZE, ordering: "-date" };
  const list = useQuery({
    queryKey: ["purchases", query],
    queryFn: () => api<Page<Purchase>>("/purchasing/purchases/", { query }),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader
        title="Kirim"
        subtitle="Omborga tovar qabul qilish"
        actions={<Button onClick={() => setOpened("new")}><Plus className="h-4 w-4" /> Yangi kirim</Button>}
      />
      <div className="w-48">
        <Select value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label="Holat">
          <option value="">Barcha holatlar</option>
          {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </Select>
      </div>
      <Card className="overflow-hidden">
        {list.isLoading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : !list.data?.results.length ? (
          <EmptyState icon={<ClipboardList className="h-6 w-6" />} title="Kirim hujjatlari yo'q" action={<Button onClick={() => setOpened("new")}>Birinchi kirim</Button>} />
        ) : (
          <>
            <Table head={<tr><Th>№</Th><Th>Sana</Th><Th>Yetkazib beruvchi</Th><Th>Ombor</Th><Th>Holat</Th><Th right>Summa</Th></tr>}>
              {list.data.results.map((p) => (
                <tr key={p.id} className="cursor-pointer hover:bg-surface-2/60" onClick={() => setOpened(p)}>
                  <Td className="font-medium num">#{p.number}{p.kind === "opening" && <span className="text-xs text-muted"> boshl.</span>}</Td>
                  <Td>{formatDate(p.date)}</Td>
                  <Td>{p.supplier_name ?? <span className="text-muted">—</span>}</Td>
                  <Td className="text-muted">{p.warehouse_name}</Td>
                  <Td><Badge tone={STATUS[p.status!]?.tone}>{STATUS[p.status!]?.label}</Badge></Td>
                  <Td right className="font-semibold">{formatNumber(p.subtotal, 2)} {p.currency}</Td>
                </tr>
              ))}
            </Table>
            <Pager page={page} count={list.data.count} size={SIZE} onPage={setPage} />
          </>
        )}
      </Card>
      {opened && <PurchaseEditor purchase={opened === "new" ? null : opened} onClose={() => setOpened(null)} />}
    </div>
  );
}
