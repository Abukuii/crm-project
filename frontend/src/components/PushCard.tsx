import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, BellRing, Send } from "lucide-react";

import { Badge, Button, Card } from "@/components/ui";
import { isIOS } from "@/components/Pwa";
import { t } from "@/i18n";
import { api } from "@/lib/api";
import {
  disablePush,
  enablePush,
  permissionState,
  PushDenied,
  pushSupported,
  type PushConfig,
} from "@/lib/push";
import { toast } from "@/stores/toast";

/** Shu qurilmada bildirishnomalarni yoqish/o'chirish (har bir xodim o'zi uchun). */
export function PushCard() {
  const qc = useQueryClient();
  const supported = pushSupported();
  const permission = permissionState();
  const standaloneIOS =
    isIOS && !window.matchMedia("(display-mode: standalone)").matches &&
    (navigator as { standalone?: boolean }).standalone !== true;

  const config = useQuery({
    queryKey: ["push-config"],
    queryFn: () => api<PushConfig>("/notifications/push/config/"),
    enabled: supported,
  });

  const refresh = () => void qc.invalidateQueries({ queryKey: ["push-config"] });

  const enable = useMutation({
    mutationFn: () => enablePush(config.data!.public_key!),
    onSuccess: () => (toast.success(t("Bildirishnomalar yoqildi")), refresh()),
    onError: (e) =>
      e instanceof PushDenied
        ? toast.error(new Error(t("Brauzer ruxsat bermadi. Sayt sozlamalaridan ruxsat bering.")))
        : toast.error(e),
  });
  const disable = useMutation({
    mutationFn: disablePush,
    onSuccess: () => (toast.success(t("Bildirishnomalar o'chirildi")), refresh()),
    onError: toast.error,
  });
  const test = useMutation({
    mutationFn: () => api<{ sent: number }>("/notifications/push/test/", { method: "POST" }),
    onSuccess: () => toast.success(t("Sinov bildirishnomasi yuborildi")),
    onError: toast.error,
  });

  const devices = config.data?.devices ?? 0;
  const active = permission === "granted" && devices > 0;

  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 font-semibold">
          {active ? <BellRing className="h-4 w-4 text-brand" /> : <Bell className="h-4 w-4 text-brand" />}
          {t("Bildirishnomalar")}
        </h2>
        {active && <Badge tone="success">{t("Yoqilgan")}</Badge>}
      </div>

      {!supported ? (
        <p className="text-sm text-muted">{t("Bu brauzer bildirishnomalarni qo'llab-quvvatlamaydi.")}</p>
      ) : !config.data?.enabled ? (
        <p className="text-sm text-muted">
          {t("Bildirishnomalar hali sozlanmagan — administrator serverda yoqishi kerak.")}
        </p>
      ) : (
        <>
          <p className="text-sm text-muted">
            {t("Yangi savdo va tovar tugashi haqida shu qurilmaga xabar keladi — sayt yopiq bo'lsa ham.")}
          </p>

          {permission === "denied" ? (
            <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
              {t("Bildirishnomalar brauzerda bloklangan. Manzil satridagi qulf belgisidan ruxsat bering.")}
            </p>
          ) : standaloneIOS ? (
            <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm text-muted">
              {t("iPhone'da avval ilovani uyga qo'shing — shundan keyin bildirishnomalar ishlaydi.")}
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {active ? (
                <>
                  <Button variant="secondary" loading={disable.isPending} onClick={() => disable.mutate()}>
                    <BellOff className="h-4 w-4" /> {t("O'chirish")}
                  </Button>
                  <Button variant="secondary" loading={test.isPending} onClick={() => test.mutate()}>
                    <Send className="h-4 w-4" /> {t("Sinov xabari")}
                  </Button>
                </>
              ) : (
                <Button loading={enable.isPending} onClick={() => enable.mutate()}>
                  <Bell className="h-4 w-4" /> {t("Bildirishnomalarni yoqish")}
                </Button>
              )}
            </div>
          )}

          {devices > 1 && (
            <p className="text-xs text-muted">{t("Ulangan qurilmalar: {n}", { n: devices })}</p>
          )}
        </>
      )}
    </Card>
  );
}
