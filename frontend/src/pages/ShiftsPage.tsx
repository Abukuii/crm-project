import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Clock, Printer } from "lucide-react";
import { useState } from "react";

import type { Page, Shift, ShiftReport } from "@/api/types";
import { Modal } from "@/components/overlay";
import { ShiftReportView } from "@/components/ShiftPanel";
import { Badge, Button, Card, EmptyState, PageHeader, Pager, Select, Skeleton, Table, Td, Th } from "@/components/ui";
import { t } from "@/i18n";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import { formatDateTime } from "@/lib/queries";

const SIZE = 30;

export function ShiftsPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [opened, setOpened] = useState<Shift | null>(null);
  const query = { status, page, page_size: SIZE };
  const list = useQuery({
    queryKey: ["shifts", query],
    queryFn: () => api<Page<Shift>>("/sales/shifts/", { query }),
    placeholderData: keepPreviousData,
  });
  const report = useQuery({
    queryKey: ["shift", opened?.id, "report"],
    queryFn: () => api<ShiftReport>(`/sales/shifts/${opened!.id}/report/`),
    enabled: !!opened,
  });

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader title={t("Smenalar")} subtitle={t("Kassa smenalari va Z-hisobotlar")} />
      <div className="w-48">
        <Select value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t("Holat")}>
          <option value="">{t("Barchasi")}</option>
          <option value="open">{t("Ochiq")}</option>
          <option value="closed">{t("Yopilgan")}</option>
        </Select>
      </div>
      <Card className="overflow-hidden">
        {list.isLoading ? (
          <Skeleton className="m-4 h-32" />
        ) : !list.data?.results.length ? (
          <EmptyState icon={<Clock className="h-6 w-6" />} title={t("Smenalar yo'q")} hint={t("Smena kassa sahifasida ochiladi")} />
        ) : (
          <>
            <Table
              head={
                <tr>
                  <Th>№</Th><Th>{t("Kassir")}</Th><Th>{t("Ochilgan")}</Th><Th>{t("Yopilgan")}</Th>
                  <Th right>{t("Kutilgan naqd")}</Th><Th right>{t("Sanalgan")}</Th><Th right>{t("Farq")}</Th>
                </tr>
              }
            >
              {list.data.results.map((s) => {
                const diff = Number(s.difference ?? 0);
                return (
                  <tr key={s.id} className="cursor-pointer hover:bg-surface-2/60" onClick={() => setOpened(s)}>
                    <Td className="font-medium num">
                      #{s.number} {s.status === "open" && <Badge tone="success">{t("ochiq")}</Badge>}
                    </Td>
                    <Td>{s.cashier_name}</Td>
                    <Td className="text-muted">{formatDateTime(s.opened_at)}</Td>
                    <Td className="text-muted">{formatDateTime(s.closed_at)}</Td>
                    <Td right>{s.expected_cash ? formatMoney(s.expected_cash) : "—"}</Td>
                    <Td right>{s.counted_cash ? formatMoney(s.counted_cash) : "—"}</Td>
                    <Td right className={cn("font-semibold", diff < 0 ? "text-danger" : diff > 0 ? "text-success" : "text-muted")}>
                      {s.difference ? formatMoney(s.difference) : "—"}
                    </Td>
                  </tr>
                );
              })}
            </Table>
            <Pager page={page} count={list.data.count} size={SIZE} onPage={setPage} />
          </>
        )}
      </Card>
      <Modal
        open={!!opened}
        onClose={() => setOpened(null)}
        size="sm"
        title={t("Smena #{n}", { n: opened?.number })}
        footer={<Button variant="secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> {t("Chop etish")}</Button>}
      >
        {report.data ? (
          <ShiftReportView report={report.data} final={opened?.status === "closed"} />
        ) : (
          <div className="h-40 animate-pulse rounded-lg bg-surface-2" />
        )}
      </Modal>
    </div>
  );
}
