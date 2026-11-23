import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Pencil, Plus, Users } from "lucide-react";
import { useState } from "react";

import { t } from "@/i18n";
import type { Page, User } from "@/api/types";
import { Modal } from "@/components/overlay";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Skeleton, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime, useRoles } from "@/lib/queries";
import { useAuth } from "@/stores/auth";
import { toast } from "@/stores/toast";

interface Branch { id: number; name: string }
type Form = { id?: number; username: string; first_name: string; last_name: string; phone: string; password: string; roles: number[]; branches: number[]; is_active: boolean };

function UserForm({ initial, onClose }: { initial: Form; onClose: () => void }) {
  const qc = useQueryClient();
  const roles = useRoles();
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => api<{ results: Branch[] }>("/tenancy/branches/").then((r) => r.results) });
  const [f, setF] = useState<Form>(initial);
  const toggle = (key: "roles" | "branches", id: number) =>
    setF({ ...f, [key]: f[key].includes(id) ? f[key].filter((x) => x !== id) : [...f[key], id] });
  const save = useMutation({
    mutationFn: () => {
      const { id, password, ...rest } = f;
      return id
        ? api(`/accounts/users/${id}/`, { method: "PATCH", body: rest })
        : api("/accounts/users/", { method: "POST", body: { ...rest, password } });
    },
    onSuccess: () => (toast.success(t("Xodim saqlandi")), void qc.invalidateQueries({ queryKey: ["users"] }), onClose()),
    onError: toast.error,
  });
  return (
    <Modal open onClose={onClose} title={f.id ? t("Xodimni tahrirlash") : t("Yangi xodim")} size="lg"
      footer={<><Button variant="secondary" onClick={onClose}>{t("Bekor")}</Button><Button loading={save.isPending} disabled={!f.username || (!f.id && f.password.length < 8) || !f.roles.length} onClick={() => save.mutate()}>{t("Saqlash")}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label={t("Login")} value={f.username} disabled={!!f.id} onChange={(e) => setF({ ...f, username: e.target.value })} autoFocus />
        {!f.id && <Input label={t("Parol (kamida 8 belgi)")} type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />}
        <Input label={t("Ism")} value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} />
        <Input label={t("Familiya")} value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} />
        <Input label={t("Telefon")} value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
      </div>
      <div className="mt-4">
        <p className="mb-2 text-sm font-medium">{t("Rollar")}</p>
        <div className="flex flex-wrap gap-2">
          {roles.data?.map((r) => (
            <button key={r.id} type="button" onClick={() => toggle("roles", r.id)}
              className={`rounded-full border px-3 py-1 text-sm ${f.roles.includes(r.id) ? "border-brand bg-brand-soft text-brand" : "border-border text-muted"}`}>
              {t(r.name)}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4">
        <p className="mb-2 text-sm font-medium">{t("Filiallar (egasidan boshqa rollar uchun majburiy)")}</p>
        <div className="flex flex-wrap gap-2">
          {branches.data?.map((b) => (
            <button key={b.id} type="button" onClick={() => toggle("branches", b.id)}
              className={`rounded-full border px-3 py-1 text-sm ${f.branches.includes(b.id) ? "border-brand bg-brand-soft text-brand" : "border-border text-muted"}`}>
              {b.name}
            </button>
          ))}
        </div>
      </div>
      {f.id && (
        <label className="mt-4 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /> {t("Faol")}
        </label>
      )}
    </Modal>
  );
}

function SecretModal({ user, kind, onClose }: { user: User; kind: "password" | "pin"; onClose: () => void }) {
  const [value, setValue] = useState("");
  const save = useMutation({
    mutationFn: () => api(`/accounts/users/${user.id}/${kind === "pin" ? "set-pin" : "set-password"}/`, { method: "POST", body: kind === "pin" ? { pin: value } : { password: value } }),
    onSuccess: () => (toast.success(kind === "pin" ? t("PIN o'rnatildi") : t("Parol o'zgartirildi")), onClose()),
    onError: toast.error,
  });
  const valid = kind === "pin" ? /^\d{4,6}$/.test(value) : value.length >= 8;
  return (
    <Modal open onClose={onClose} size="sm" title={`${user.username}: ${kind === "pin" ? t("kassa PIN") : t("yangi parol")}`}
      footer={<><Button variant="secondary" onClick={onClose}>{t("Bekor")}</Button><Button disabled={!valid} loading={save.isPending} onClick={() => save.mutate()}>{t("Saqlash")}</Button></>}>
      <Input type="password" autoComplete="new-password" inputMode={kind === "pin" ? "numeric" : undefined} label={kind === "pin" ? t("4–6 raqam") : t("Kamida 8 belgi")} value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
    </Modal>
  );
}

export function UsersPage() {
  const { user: me } = useAuth();
  const [editing, setEditing] = useState<Form | null>(null);
  const [secret, setSecret] = useState<{ user: User; kind: "password" | "pin" } | null>(null);
  const list = useQuery({ queryKey: ["users"], queryFn: () => api<Page<User>>("/accounts/users/", { query: { page_size: 200 } }) });
  const roles = useRoles();
  const roleName = (id: number) => roles.data?.find((r) => r.id === id)?.name ?? id;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHeader title={t("Xodimlar")}
        actions={<Button onClick={() => setEditing({ username: "", first_name: "", last_name: "", phone: "", password: "", roles: [], branches: [], is_active: true })}><Plus className="h-4 w-4" /> {t("Xodim")}</Button>} />
      <Card className="overflow-hidden">
        {list.isLoading ? <Skeleton className="m-4 h-32" /> : !list.data?.results.length ? <EmptyState icon={<Users className="h-6 w-6" />} title={t("Xodim yo'q")} /> : (
          <Table head={<tr><Th>{t("Login")}</Th><Th>{t("Ism")}</Th><Th>{t("Rollar")}</Th><Th>{t("Oxirgi kirish")}</Th><Th>{t("Holat")}</Th><Th /></tr>}>
            {list.data.results.map((u) => (
              <tr key={u.id} className="hover:bg-surface-2/60">
                <Td className="font-medium">{u.username}{u.id === me?.id && <span className="text-xs text-muted"> {t("(siz)")}</span>}</Td>
                <Td>{[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}</Td>
                <Td><div className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r} tone="brand">{t(String(roleName(r)))}</Badge>)}</div></Td>
                <Td className="text-muted">{formatDateTime(u.last_login)}</Td>
                <Td>{u.is_active ? <Badge tone="success">{t("faol")}</Badge> : <Badge tone="danger">{t("o'chirilgan")}</Badge>}</Td>
                <Td>
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setSecret({ user: u, kind: "pin" })}>{t("PIN")}</Button>
                    <Button variant="ghost" size="icon" aria-label={t("Parol")} onClick={() => setSecret({ user: u, kind: "password" })}><KeyRound className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" aria-label={t("Tahrirlash")} onClick={() => setEditing({ id: u.id, username: u.username, first_name: u.first_name ?? "", last_name: u.last_name ?? "", phone: u.phone ?? "", password: "", roles: u.roles, branches: u.branches ?? [], is_active: u.is_active ?? true })}><Pencil className="h-4 w-4" /></Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing && <UserForm initial={editing} onClose={() => setEditing(null)} />}
      {secret && <SecretModal {...secret} onClose={() => setSecret(null)} />}
    </div>
  );
}
