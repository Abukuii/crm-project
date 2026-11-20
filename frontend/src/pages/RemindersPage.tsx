import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, Plus, StickyNote, Trash2 } from "lucide-react";
import { useState } from "react";

import type { Reminder } from "@/api/types";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/queries";
import { toast } from "@/stores/toast";

const LEVELS = { normal: { label: "Oddiy", tone: "neutral" }, important: { label: "Muhim", tone: "warning" }, urgent: { label: "Shoshilinch", tone: "danger" } } as const;

export function RemindersPage() {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [level, setLevel] = useState<keyof typeof LEVELS>("normal");
  const [due, setDue] = useState("");
  const list = useQuery({ queryKey: ["reminders"], queryFn: () => api<Reminder[]>("/notes/reminders/") });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["reminders"] });
  const add = useMutation({
    mutationFn: () => api("/notes/reminders/", { method: "POST", body: { text, level, due_date: due || null } }),
    onSuccess: () => (setText(""), setDue(""), refresh()),
    onError: toast.error,
  });
  const toggle = useMutation({
    mutationFn: (r: Reminder) => api(`/notes/reminders/${r.id}/`, { method: "PATCH", body: { is_done: !r.is_done } }),
    onSuccess: refresh,
    onError: toast.error,
  });
  const remove = useMutation({ mutationFn: (id: number) => api(`/notes/reminders/${id}/`, { method: "DELETE" }), onSuccess: refresh, onError: toast.error });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader title="Eslatmalar" />
      <Card className="p-4">
        <form className="grid gap-2 sm:grid-cols-[1fr_150px_150px_auto]" onSubmit={(e) => (e.preventDefault(), text.trim() && add.mutate())}>
          <Input placeholder="Yangi eslatma…" value={text} onChange={(e) => setText(e.target.value)} aria-label="Matn" />
          <Select value={level} onChange={(e) => setLevel(e.target.value as keyof typeof LEVELS)} aria-label="Muhimlik">
            {Object.entries(LEVELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </Select>
          <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="Muddat" />
          <Button type="submit" loading={add.isPending} disabled={!text.trim()}><Plus className="h-4 w-4" /></Button>
        </form>
      </Card>
      <Card>
        {!list.data?.length ? (
          <EmptyState icon={<StickyNote className="h-6 w-6" />} title="Eslatma yo'q" />
        ) : (
          <ul className="divide-y divide-border">
            {list.data.map((r) => (
              <li key={r.id} className="anim-slide-up flex items-start gap-3 p-4">
                <button onClick={() => toggle.mutate(r)} className={r.is_done ? "text-success" : "text-muted hover:text-brand"} aria-label="Bajarildi">
                  {r.is_done ? <CheckCircle2 className="h-5 w-5" /> : <Circle className="h-5 w-5" />}
                </button>
                <div className="flex-1">
                  <p className={cn("text-sm", r.is_done && "text-muted line-through")}>{r.text}</p>
                  <p className="mt-1 flex items-center gap-2 text-xs text-muted">
                    <Badge tone={LEVELS[r.level as keyof typeof LEVELS]?.tone ?? "neutral"}>{LEVELS[r.level as keyof typeof LEVELS]?.label}</Badge>
                    {r.due_date && <span>Muddat: {formatDate(r.due_date)}</span>}
                    <span>{r.created_by_name}</span>
                  </p>
                </div>
                <button onClick={() => remove.mutate(r.id)} className="text-muted hover:text-danger" aria-label="O'chirish"><Trash2 className="h-4 w-4" /></button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
