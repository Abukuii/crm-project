import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Send } from "lucide-react";
import { useEffect, useState } from "react";

import { t } from "@/i18n";
import type { Me, Tenant } from "@/api/types";
import { Button, Card, Input, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { useTheme, type Theme } from "@/stores/theme";
import { toast } from "@/stores/toast";

type Settings = { negative_stock: string; rate_source: string; telegram_chat_id: string; telegram_notify_sales: boolean; require_shift: boolean };

export function SettingsPage() {
  const qc = useQueryClient();
  const tenant = useQuery({ queryKey: ["tenant"], queryFn: () => api<Tenant>("/tenancy/current/") });
  const [info, setInfo] = useState({ name: "", inn: "", phone: "", address: "" });
  const [s, setS] = useState<Settings>({ negative_stock: "forbid", rate_source: "cbu", telegram_chat_id: "", telegram_notify_sales: true, require_shift: false });

  useEffect(() => {
    if (!tenant.data) return;
    const t = tenant.data;
    setInfo({ name: t.name, inn: t.inn ?? "", phone: t.phone ?? "", address: t.address ?? "" });
    const eff = t.effective_settings as unknown as Settings;
    setS({ ...eff, telegram_chat_id: String(eff.telegram_chat_id ?? "") });
  }, [tenant.data]);

  const save = useMutation({
    mutationFn: () => api<Tenant>("/tenancy/current/", { method: "PATCH", body: { ...info, settings: s } }),
    onSuccess: () => {
      toast.success(t("Sozlamalar saqlandi"));
      void qc.invalidateQueries({ queryKey: ["tenant"] });
      void qc.invalidateQueries({ queryKey: ["rate"] });
    },
    onError: toast.error,
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader title={t("Sozlamalar")} actions={<Button loading={save.isPending} onClick={() => save.mutate()}>{t("Saqlash")}</Button>} />
      <Card className="space-y-3 p-5">
        <h2 className="flex items-center gap-2 font-semibold"><Building2 className="h-4 w-4 text-brand" /> {t("Do'kon ma'lumotlari")}</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label={t("Nomi (chekda ko'rinadi)")} value={info.name} onChange={(e) => setInfo({ ...info, name: e.target.value })} />
          <Input label={t("INN")} value={info.inn} onChange={(e) => setInfo({ ...info, inn: e.target.value })} />
          <Input label={t("Telefon")} value={info.phone} onChange={(e) => setInfo({ ...info, phone: e.target.value })} />
          <Input label={t("Manzil")} value={info.address} onChange={(e) => setInfo({ ...info, address: e.target.value })} />
        </div>
      </Card>
      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">{t("Savdo va ombor")}</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label={t("Qoldiq yetmasa")} value={s.negative_stock} onChange={(e) => setS({ ...s, negative_stock: e.target.value })}>
            <option value="forbid">{t("Sotishni taqiqlash (tavsiya)")}</option>
            <option value="allow">{t("Minusga sotishga ruxsat")}</option>
          </Select>
          <Select label={t("Dollar kursi manbai")} value={s.rate_source} onChange={(e) => setS({ ...s, rate_source: e.target.value })}>
            <option value="cbu">{t("Markaziy bank (avtomatik)")}</option>
            <option value="manual">{t("Do'kon kursi (qo'lda)")}</option>
          </Select>
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={s.require_shift} onChange={(e) => setS({ ...s, require_shift: e.target.checked })} />
          <span>
            {t("Smena ochilmasa sotishni taqiqlash")}
            <span className="block text-xs text-muted">{t("Kassir avval smenani ochadi, kun oxirida Z-hisobot bilan yopadi")}</span>
          </span>
        </label>
      </Card>
      <Card className="space-y-3 p-5">
        <h2 className="flex items-center gap-2 font-semibold"><Send className="h-4 w-4 text-brand" /> {t("Telegram xabarlari")}</h2>
        <p className="text-sm text-muted">{t("Botni guruh yoki kanalga qo'shing va uning ID'sini kiriting (masalan, -1001234567890). Har bir savdo haqida xabar keladi.")}</p>
        <Input label={t("Guruh / kanal ID")} value={s.telegram_chat_id} onChange={(e) => setS({ ...s, telegram_chat_id: e.target.value })} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={s.telegram_notify_sales} onChange={(e) => setS({ ...s, telegram_notify_sales: e.target.checked })} />
          {t("Har bir savdo haqida xabar yuborish")}
        </label>
      </Card>
    </div>
  );
}

export function ProfilePage() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const [f, setF] = useState({ first_name: user?.first_name ?? "", last_name: user?.last_name ?? "", phone: user?.phone ?? "" });
  const save = useMutation({
    mutationFn: () => api<Me>("/auth/me/", { method: "PATCH", body: { ...f, theme } }),
    onSuccess: (me) => (useAuth.setState({ user: me }), toast.success(t("Profil yangilandi"))),
    onError: toast.error,
  });
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <PageHeader title={t("Profil")} subtitle={`${user?.username} · ${user?.roles.map((r) => t(r.name)).join(", ")}`} />
      <Card className="space-y-3 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label={t("Ism")} value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} />
          <Input label={t("Familiya")} value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} />
          <Input label={t("Telefon")} value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
          <Select label={t("Mavzu")} value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
            <option value="system">{t("Tizim bo'yicha")}</option><option value="light">{t("Yorug'")}</option><option value="dark">{t("Tun rejimi")}</option>
          </Select>
        </div>
        <Button loading={save.isPending} onClick={() => save.mutate()}>{t("Saqlash")}</Button>
      </Card>
    </div>
  );
}
