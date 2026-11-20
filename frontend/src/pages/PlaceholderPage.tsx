import { Construction } from "lucide-react";

import { Card, EmptyState } from "@/components/ui";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <Card>
        <EmptyState
          icon={<Construction className="h-6 w-6" />}
          title="Bu bo'lim ishlab chiqilmoqda"
          hint="TZ bo'yicha keyingi bosqichlarda qo'shiladi"
        />
      </Card>
    </div>
  );
}
