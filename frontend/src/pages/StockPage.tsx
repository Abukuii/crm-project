import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Boxes, Search } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import type { Page, StockBalance } from "@/api/types";
import { Badge, Card, EmptyState, Input, PageHeader, Pager, Select, Skeleton, Table, Td, Th } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, formatQty } from "@/lib/format";
import { useWarehouses } from "@/lib/queries";

const SIZE = 50;

export function StockPage() {
  const [params, setParams] = useSearchParams();
  const low = params.get("low_stock") === "true";
  const [search, setSearch] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [page, setPage] = useState(1);
  const warehouses = useWarehouses();
  const debounced = useDebounced(search);
  const query = { search: debounced, warehouse, low_stock: low || undefined, page, page_size: SIZE };
  const list = useQuery({
    queryKey: ["balances", query],
    queryFn: () => api<Page<StockBalance>>("/inventory/balances/", { query }),
    placeholderData: keepPreviousData,
  });
  const showCost = list.data?.results[0]?.avg_cost !== undefined;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader title="Qoldiqlar" subtitle={list.data ? `${list.data.count} ta pozitsiya` : undefined} />
      <div className="flex flex-wrap items-end gap-2">
        <button
          onClick={() => (setPage(1), setParams(low ? {} : { low_stock: "true" }))}
          className={cn("flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium", low ? "bg-warning text-white" : "bg-surface-2 text-muted hover:text-fg")}
        >
          <AlertTriangle className="h-4 w-4" /> Kam qolganlar
        </button>
        {(warehouses.data?.length ?? 0) > 1 && (
          <div className="w-48">
            <Select value={warehouse} onChange={(e) => (setWarehouse(e.target.value), setPage(1))} aria-label="Ombor">
              <option value="">Barcha omborlar</option>
              {warehouses.data!.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </div>
        )}
        <div className="ml-auto w-full sm:w-80">
          <Input placeholder="Mahsulot nomi" icon={<Search className="h-4 w-4" />} value={search} onChange={(e) => (setSearch(e.target.value), setPage(1))} aria-label="Qidiruv" />
        </div>
      </div>
      <Card className="overflow-hidden">
        {list.isLoading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : !list.data?.results.length ? (
          <EmptyState icon={<Boxes className="h-6 w-6" />} title={low ? "Kam qolgan mahsulot yo'q" : "Qoldiq yo'q"} hint="Kirim hujjati yoki Excel import orqali qoldiq kiriting" />
        ) : (
          <>
            <Table
              head={
                <tr>
                  <Th>Mahsulot</Th><Th>Ombor</Th><Th right>Qoldiq</Th><Th right>Min.</Th>
                  {showCost && <><Th right>O'rtacha tannarx</Th><Th right>Qiymati</Th></>}
                </tr>
              }
            >
              {list.data.results.map((b) => {
                const qty = Number(b.qty);
                const min = Number(b.min_stock);
                return (
                  <tr key={b.id} className="hover:bg-surface-2/60">
                    <Td className="font-medium">{b.product_name} <span className="text-xs text-muted">{b.product_sku}</span></Td>
                    <Td className="text-muted">{b.warehouse_name}</Td>
                    <Td right>
                      <span className={cn("font-semibold", qty <= 0 ? "text-danger" : qty <= min ? "text-warning" : "")}>{formatQty(b.qty, b.unit)}</span>
                      {qty <= min && <Badge tone={qty <= 0 ? "danger" : "warning"}>{qty <= 0 ? "tugagan" : "kam"}</Badge>}
                    </Td>
                    <Td right className="text-muted">{formatQty(b.min_stock)}</Td>
                    {showCost && <><Td right>{formatMoney(b.avg_cost)}</Td><Td right>{formatMoney(b.total_cost)}</Td></>}
                  </tr>
                );
              })}
            </Table>
            <Pager page={page} count={list.data.count} size={SIZE} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
