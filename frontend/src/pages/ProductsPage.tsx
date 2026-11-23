import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileSpreadsheet, Package, Pencil, Plus, Search, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { t } from "@/i18n";
import type { ImportResult, PaginatedProducts, Product } from "@/api/types";
import { Modal } from "@/components/overlay";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Pager, Select, Skeleton, Table, Td, Textarea, Th } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api, apiDownload, apiUpload } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { useCategories, usePriceTypes, useUnits, useWarehouses } from "@/lib/queries";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

const PAGE_SIZE = 50;

interface FormState {
  id?: number;
  name: string;
  sku: string;
  category: number | null;
  base_unit: number | null;
  price_currency: "UZS" | "USD";
  min_stock: string;
  mxik_code: string;
  description: string;
  barcodes: string;
  units: { unit: number; factor: string; barcode: string }[];
  prices: Record<number, string>;
}

function toForm(p?: Product): FormState {
  return {
    id: p?.id,
    name: p?.name ?? "",
    sku: p?.sku ?? "",
    category: p?.category ?? null,
    base_unit: p?.base_unit ?? null,
    price_currency: (p?.price_currency as "UZS" | "USD") ?? "UZS",
    min_stock: p?.min_stock ?? "0",
    mxik_code: p?.mxik_code ?? "",
    description: p?.description ?? "",
    barcodes: (p?.barcodes ?? []).join(", "),
    units: (p?.units ?? []).map((u) => ({ unit: u.unit, factor: u.factor, barcode: u.barcode ?? "" })),
    prices: Object.fromEntries((p?.prices ?? []).map((x) => [x.price_type, x.amount])),
  };
}

function ProductForm({ product, onClose }: { product?: Product; onClose: () => void }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const units = useUnits();
  const categories = useCategories();
  const priceTypes = usePriceTypes();
  const [f, setF] = useState<FormState>(() => toForm(product));
  const set = (patch: Partial<FormState>) => setF({ ...f, ...patch });

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        name: f.name, sku: f.sku, category: f.category, base_unit: f.base_unit, price_currency: f.price_currency,
        min_stock: f.min_stock || "0", mxik_code: f.mxik_code, description: f.description,
        barcodes: f.barcodes.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean),
        units: f.units.filter((u) => u.unit && Number(u.factor) > 0).map((u) => ({ ...u, barcode: u.barcode || null })),
      };
      if (can("price.edit")) {
        body.prices = Object.entries(f.prices)
          .filter(([, v]) => v !== "" && v !== undefined)
          .map(([k, v]) => ({ price_type: Number(k), amount: v }));
      }
      return f.id
        ? api<Product>(`/catalog/products/${f.id}/`, { method: "PATCH", body })
        : api<Product>("/catalog/products/", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(t("Mahsulot saqlandi"));
      void qc.invalidateQueries({ queryKey: ["products"] });
      void qc.invalidateQueries({ queryKey: ["categories"] });
      onClose();
    },
    onError: toast.error,
  });

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={f.id ? t("Mahsulotni tahrirlash") : t("Yangi mahsulot")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("Bekor")}</Button>
          <Button loading={save.isPending} disabled={!f.name.trim() || !f.base_unit} onClick={() => save.mutate()}>{t("Saqlash")}</Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><Input label={t("Nomi")} value={f.name} onChange={(e) => set({ name: e.target.value })} autoFocus /></div>
        <Input label={t("Artikul (bo'sh — avtomatik)")} value={f.sku} onChange={(e) => set({ sku: e.target.value })} />
        <Select label={t("Kategoriya")} value={f.category ?? ""} onChange={(e) => set({ category: e.target.value ? Number(e.target.value) : null })}>
          <option value="">—</option>
          {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select label={t("Asosiy birlik")} value={f.base_unit ?? ""} onChange={(e) => set({ base_unit: Number(e.target.value) })}>
          <option value="" disabled>{t("Tanlang")}</option>
          {units.data?.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.short})</option>)}
        </Select>
        <Select label={t("Narx valyutasi")} value={f.price_currency} onChange={(e) => set({ price_currency: e.target.value as "UZS" | "USD" })}>
          <option value="UZS">{t("So'm")}</option>
          <option value="USD">{t("Dollar")}</option>
        </Select>
        <Input label={t("Minimal qoldiq")} type="number" min={0} value={f.min_stock} onChange={(e) => set({ min_stock: e.target.value })} />
        <Input label={t("MXIK (IKPU) kodi")} value={f.mxik_code} onChange={(e) => set({ mxik_code: e.target.value })} />
        <div className="sm:col-span-2"><Input label={t("Shtrix-kodlar (vergul bilan)")} value={f.barcodes} onChange={(e) => set({ barcodes: e.target.value })} /></div>
      </div>

      {can("price.edit") && (
        <div className="mt-5">
          <h3 className="mb-2 text-sm font-semibold">Narxlar ({f.price_currency === "USD" ? "dollar" : "so'm"}, 1 asosiy birlik)</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            {priceTypes.data?.map((pt) => (
              <Input key={pt.id} label={pt.name} type="number" min={0} step="any" value={f.prices[pt.id] ?? ""}
                onChange={(e) => set({ prices: { ...f.prices, [pt.id]: e.target.value } })} />
            ))}
          </div>
        </div>
      )}

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{t("Qo'shimcha birliklar")}</h3>
          <Button variant="ghost" size="sm" onClick={() => set({ units: [...f.units, { unit: 0, factor: "", barcode: "" }] })}>
            <Plus className="h-4 w-4" /> {t("Birlik")}
          </Button>
        </div>
        {f.units.length === 0 && <p className="text-xs text-muted">Masalan: 1 pachka = 10 dona, 1 rulon = 100 m</p>}
        <div className="space-y-2">
          {f.units.map((u, i) => (
            <div key={i} className="grid grid-cols-[1fr_110px_1fr_auto] items-end gap-2">
              <Select aria-label={t("Birlik")} value={u.unit || ""} onChange={(e) => set({ units: f.units.map((x, j) => (j === i ? { ...x, unit: Number(e.target.value) } : x)) })}>
                <option value="" disabled>{t("Birlik")}</option>
                {units.data?.filter((x) => x.id !== f.base_unit).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </Select>
              <Input aria-label={t("Koeffitsient")} placeholder={t("= nechta")} type="number" value={u.factor} onChange={(e) => set({ units: f.units.map((x, j) => (j === i ? { ...x, factor: e.target.value } : x)) })} />
              <Input aria-label={t("Shtrix-kod")} placeholder={t("Shtrix-kod")} value={u.barcode} onChange={(e) => set({ units: f.units.map((x, j) => (j === i ? { ...x, barcode: e.target.value } : x)) })} />
              <Button variant="ghost" size="icon" onClick={() => set({ units: f.units.filter((_, j) => j !== i) })} aria-label={t("O'chirish")}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5"><Textarea label={t("Tavsif")} value={f.description} onChange={(e) => set({ description: e.target.value })} /></div>
    </Modal>
  );
}

function ImportModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const warehouses = useWarehouses();
  const [file, setFile] = useState<File | null>(null);
  const [warehouse, setWarehouse] = useState<string>("");
  const [preview, setPreview] = useState<ImportResult | null>(null);

  const run = useMutation({
    mutationFn: (dryRun: boolean) => {
      const form = new FormData();
      form.append("file", file!);
      form.append("dry_run", String(dryRun));
      if (warehouse) form.append("warehouse", warehouse);
      return apiUpload<ImportResult>("/dataio/products/import/", form);
    },
    onSuccess: (res) => {
      if (res.dry_run) {
        setPreview(res);
        return;
      }
      toast.success(t("Import tugadi: {c} ta yangi, {u} ta yangilandi", { c: res.created, u: res.updated }));
      void qc.invalidateQueries({ queryKey: ["products"] });
      void qc.invalidateQueries({ queryKey: ["balances"] });
      onClose();
    },
    onError: toast.error,
  });

  const errors = preview?.rows.filter((r) => r.errors.length) ?? [];

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={t("Excel'dan import")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("Yopish")}</Button>
          {!preview ? (
            <Button disabled={!file} loading={run.isPending} onClick={() => run.mutate(true)}>{t("Tekshirish")}</Button>
          ) : (
            <Button disabled={errors.length > 0} loading={run.isPending} onClick={() => run.mutate(false)}>
              Import qilish ({preview.total})
            </Button>
          )}
        </>
      }
    >
      <ol className="space-y-4 text-sm">
        <li className="flex items-center justify-between gap-3 rounded-xl bg-surface-2 p-3">
          <span><b>1.</b> {t("Shablonni yuklab oling va to'ldiring")}</span>
          <Button variant="secondary" size="sm" onClick={() => apiDownload("/dataio/products/template/", "mahsulotlar_shablon.xlsx").catch(toast.error)}>
            <FileSpreadsheet className="h-4 w-4" /> {t("Shablon")}
          </Button>
        </li>
        <li className="space-y-2 rounded-xl bg-surface-2 p-3">
          <p><b>2.</b> {t("Faylni tanlang (.xlsx)")}</p>
          <input
            type="file"
            accept=".xlsx"
            onChange={(e) => (setFile(e.target.files?.[0] ?? null), setPreview(null))}
            className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand file:px-3 file:py-2 file:text-on-brand"
          />
          {(warehouses.data?.length ?? 0) > 1 && (
            <Select label={t("Boshlang'ich qoldiq qaysi omborga")} value={warehouse} onChange={(e) => setWarehouse(e.target.value)}>
              <option value="">{t("Asosiy")}</option>
              {warehouses.data!.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          )}
        </li>
      </ol>
      {preview && (
        <div className="anim-slide-up mt-4 space-y-3">
          <div className="flex gap-2">
            <Badge tone="brand">{t("Jami")}: {preview.total}</Badge>
            <Badge tone="success">{t("Yangi")}: {preview.rows.filter((r) => r.action === "create").length}</Badge>
            <Badge>{t("Yangilanadi")}: {preview.rows.filter((r) => r.action === "update").length}</Badge>
            {errors.length > 0 && <Badge tone="danger">{t("Xato")}: {errors.length}</Badge>}
          </div>
          {errors.length > 0 ? (
            <div className="max-h-64 overflow-auto rounded-xl border border-danger/40">
              <Table head={<tr><Th>{t("Qator")}</Th><Th>{t("Nomi")}</Th><Th>{t("Xato")}</Th></tr>}>
                {errors.map((r) => (
                  <tr key={r.line}>
                    <Td className="num">{r.line}</Td>
                    <Td>{r.name || "—"}</Td>
                    <Td className="text-danger">{r.errors.join("; ")}</Td>
                  </tr>
                ))}
              </Table>
            </div>
          ) : (
            <p className="rounded-lg bg-success/10 px-3 py-2 text-success">{t("Xato topilmadi — import qilishga tayyor.")}</p>
          )}
        </div>
      )}
    </Modal>
  );
}

export function ProductsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const page = Number(params.get("page") ?? "1");
  const debounced = useDebounced(search);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [importing, setImporting] = useState(false);

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["products", { search: debounced, page }],
    queryFn: ({ signal }) =>
      api<PaginatedProducts>("/catalog/products/", { query: { search: debounced, page, page_size: PAGE_SIZE, is_archived: false }, signal }),
    placeholderData: keepPreviousData,
  });

  const archive = useMutation({
    mutationFn: (p: Product) => api(`/catalog/products/${p.id}/`, { method: "DELETE" }),
    onSuccess: () => (toast.success(t("Mahsulot arxivlandi")), void qc.invalidateQueries({ queryKey: ["products"] })),
    onError: toast.error,
  });

  const update = (next: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) (v ? p.set(k, v) : p.delete(k));
    setParams(p, { replace: true });
  };

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader
        title={t("Mahsulotlar")}
        subtitle={data ? t("{n} ta mahsulot", { n: data.count }) : " "}
        actions={
          <>
            <Button variant="secondary" onClick={() => apiDownload("/dataio/products/export/", "mahsulotlar.xlsx").catch(toast.error)}>
              <Download className="h-4 w-4" /> {t("Excel")}
            </Button>
            {can("catalog.manage") && (
              <>
                <Button variant="secondary" onClick={() => setImporting(true)}><Upload className="h-4 w-4" /> {t("Import")}</Button>
                <Button onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> {t("Mahsulot")}</Button>
              </>
            )}
          </>
        }
      />
      <div className="w-full sm:w-96">
        <Input
          placeholder={t("Nomi, artikul yoki shtrix-kod…")}
          icon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(e) => update({ search: e.target.value || null, page: null })}
          aria-label={t("Mahsulot qidirish")}
        />
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : isError ? (
          <EmptyState icon={<Package className="h-6 w-6" />} title={t("Ma'lumotni yuklab bo'lmadi")} />
        ) : !data?.results.length ? (
          <EmptyState
            icon={<Package className="h-6 w-6" />}
            title={search ? t("Hech narsa topilmadi") : t("Hali mahsulot yo'q")}
            hint={search ? t("Kirill va lotin farqi yo'q — boshqa so'z bilan qidiring") : t("Mahsulot qo'shing yoki Excel'dan import qiling")}
          />
        ) : (
          <div className={isFetching ? "opacity-60 transition-opacity" : undefined}>
            <Table head={<tr><Th>{t("Nomi")}</Th><Th>{t("Artikul")}</Th><Th>{t("Kategoriya")}</Th><Th>{t("Birlik")}</Th><Th right>{t("Narx")}</Th><Th /></tr>}>
              {data.results.map((p) => {
                const price = p.prices?.[0];
                return (
                  <tr key={p.id} className="hover:bg-surface-2/60">
                    <Td className="font-medium">{p.name}</Td>
                    <Td className="text-muted num">{p.sku}</Td>
                    <Td>{p.category_name ?? <span className="text-muted">—</span>}</Td>
                    <Td>
                      <Badge>{p.base_unit_short}</Badge>{" "}
                      {p.units?.map((u) => <Badge key={u.unit} tone="brand">{u.unit_short}={Number(u.factor)}</Badge>)}
                    </Td>
                    <Td right>{price ? formatMoney(price.amount, p.price_currency) : <span className="text-muted">—</span>}</Td>
                    <Td>
                      {can("catalog.manage") && (
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setEditing(p)} aria-label={t("Tahrirlash")}><Pencil className="h-4 w-4" /></Button>
                          <Button variant="ghost" size="icon" aria-label={t("Arxivlash")}
                            onClick={() => window.confirm(t("'{name}' arxivlansinmi? Tarix saqlanadi.", { name: p.name })) && archive.mutate(p)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </Td>
                  </tr>
                );
              })}
            </Table>
            <Pager page={page} count={data.count} size={PAGE_SIZE} onPage={(p) => update({ page: String(p) })} />
          </div>
        )}
      </Card>
      {editing && <ProductForm product={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} />}
      {importing && <ImportModal onClose={() => setImporting(false)} />}
    </div>
  );
}
