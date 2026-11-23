import { Languages } from "lucide-react";

import { LANGS, t, useLang, type Lang } from "@/i18n";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useAuth } from "@/stores/auth";

/** UZ / RU / EN almashtirgich. Kirgan foydalanuvchi uchun tanlov profilga ham saqlanadi. */
export function LangSwitcher({ className }: { className?: string }) {
  const { lang, setLang } = useLang();
  const status = useAuth((s) => s.status);

  const change = (code: Lang) => {
    if (code === lang) return;
    setLang(code);
    if (status === "authenticated") {
      void api("/auth/me/", { method: "PATCH", body: { language: code } }).catch(() => undefined);
    }
  };

  return (
    <div className={cn("flex items-center gap-0.5 rounded-lg border border-border bg-surface-2/60 p-0.5", className)} role="group" aria-label={t("Til")}>
      <Languages className="mx-1 hidden h-3.5 w-3.5 text-muted sm:block" aria-hidden />
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => change(l.code)}
          title={l.label}
          aria-pressed={lang === l.code}
          className={cn(
            "rounded-md px-2 py-1 text-xs font-semibold transition-colors",
            lang === l.code ? "bg-brand text-on-brand shadow-sm" : "text-muted hover:text-fg",
          )}
        >
          {l.short}
        </button>
      ))}
    </div>
  );
}
