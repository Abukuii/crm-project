import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";

import type { PaginatedProducts, Product } from "@/api/types";
import { Input } from "@/components/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { api } from "@/lib/api";

/** Mahsulot qidirib tanlash (nom, artikul yoki shtrix-kod). Enter — birinchi natija. */
export function ProductPicker({ onPick, placeholder = "Mahsulot qo'shish: nom yoki shtrix-kod" }: { onPick: (p: Product) => void; placeholder?: string }) {
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const debounced = useDebounced(term, 200);
  const q = useQuery({
    queryKey: ["products", "pick", debounced],
    queryFn: () => api<PaginatedProducts>("/catalog/products/", { query: { search: debounced, page_size: 10, is_archived: false } }),
    enabled: open && debounced.length > 0,
  });
  const pick = (p: Product) => {
    onPick(p);
    setTerm("");
  };
  return (
    <div className="relative">
      <Input
        placeholder={placeholder}
        icon={<Search className="h-4 w-4" />}
        value={term}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => setTerm(e.target.value)}
        onKeyDown={(e) => {
          const first = q.data?.results[0];
          if (e.key === "Enter" && first) {
            e.preventDefault();
            pick(first);
          }
        }}
        aria-label="Mahsulot qidirish"
      />
      {open && (q.data?.results.length ?? 0) > 0 && (
        <ul className="anim-pop absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-border bg-surface p-1 shadow-xl">
          {q.data!.results.map((p) => (
            <li key={p.id}>
              <button className="flex w-full justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2" onMouseDown={() => pick(p)}>
                <span>{p.name}</span>
                <span className="text-muted">{p.sku} · {p.base_unit_short}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
