import {
  BarChart3,
  Boxes,
  ChevronsLeft,
  Clock,
  ClipboardList,
  HandCoins,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Package,
  Receipt,
  Settings,
  ShoppingCart,
  StickyNote,
  Sun,
  Truck,
  UserCog,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { t } from "@/i18n";
import { LangSwitcher } from "@/components/LangSwitcher";
import { InstallButton } from "@/components/Pwa";
import { ContactInfo } from "@/components/ContactInfo";
import { Toaster } from "@/components/overlay";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { syncPushSubscription } from "@/lib/push";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  perm?: string;
}

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Savdo",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard },
      { to: "/pos", label: "Kassa", icon: ShoppingCart, perm: "sales.create" },
      { to: "/sales", label: "Savdo tarixi", icon: Receipt, perm: "sales.create" },
      { to: "/shifts", label: "Smenalar", icon: Clock, perm: "sales.create" },
      { to: "/customers", label: "Mijozlar va qarzlar", icon: HandCoins, perm: "customers.view" },
    ],
  },
  {
    group: "Ombor",
    items: [
      { to: "/products", label: "Mahsulotlar", icon: Package, perm: "catalog.view" },
      { to: "/stock", label: "Qoldiqlar", icon: Boxes, perm: "inventory.view" },
      { to: "/purchases", label: "Kirim", icon: ClipboardList, perm: "inventory.manage" },
      { to: "/suppliers", label: "Yetkazib beruvchilar", icon: Truck, perm: "inventory.view" },
    ],
  },
  {
    group: "Boshqaruv",
    items: [
      { to: "/expenses", label: "Xarajatlar", icon: Wallet, perm: "expenses.manage" },
      { to: "/reminders", label: "Eslatmalar", icon: StickyNote, perm: "reminders.manage" },
      { to: "/users", label: "Xodimlar", icon: Users, perm: "users.manage" },
      { to: "/settings", label: "Sozlamalar", icon: Settings, perm: "settings.manage" },
    ],
  },
];

const THEME_ICON = { system: Monitor, light: Sun, dark: Moon } as const;
const THEME_LABEL = { system: "Tizim mavzusi", light: "Yorug' mavzu", dark: "Tun mavzusi" } as const;

export function AppLayout() {
  const { user, logout, can } = useAuth();
  // Obuna "jim" yo'qolmasligi uchun har safar ochilganda server bilan solishtiriladi
  useEffect(() => {
    void syncPushSubscription();
  }, []);
  const { theme, cycle } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const ThemeIcon = THEME_ICON[theme];

  const sidebar = (
    <nav className="flex h-full flex-col gap-6 overflow-y-auto p-3" aria-label={t("Asosiy menyu")}>
      {NAV.map(({ group, items }) => {
        const visible = items.filter((i) => !i.perm || can(i.perm));
        if (!visible.length) return null;
        return (
          <div key={group} className="space-y-1">
            {!collapsed && <p className="px-3 text-xs font-semibold uppercase tracking-wide text-muted">{t(group)}</p>}
            {visible.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                onClick={() => setMobileOpen(false)}
                title={collapsed ? t(label) : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                    isActive ? "bg-brand-soft text-brand" : "text-muted hover:bg-surface-2 hover:text-fg",
                    collapsed && "justify-center px-0",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                {!collapsed && <span className="truncate">{t(label)}</span>}
              </NavLink>
            ))}
          </div>
        );
      })}
    </nav>
  );

  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username;

  return (
    <div className="flex min-h-dvh">
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200 md:flex print:hidden",
          collapsed ? "w-16" : "w-64",
        )}
      >
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
          <img src="/savdo-icon.svg" width="32" height="32" alt={collapsed ? "Savdo" : ""} className="shrink-0" />
          {!collapsed && (
            <div className="min-w-0 leading-tight">
              <p className="font-semibold">Savdo</p>
              <p className="truncate text-xs text-muted">{user?.tenant?.name}</p>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-hidden">{sidebar}</div>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="flex h-10 items-center justify-center border-t border-border text-muted hover:text-fg"
          aria-label={collapsed ? t("Menyuni ochish") : t("Menyuni yig'ish")}
        >
          <ChevronsLeft className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />
        </button>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal>
          <div className="anim-fade absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="anim-slide-up absolute inset-y-0 left-0 w-72 bg-surface shadow-xl">{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-surface/80 px-4 backdrop-blur print:hidden">
          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileOpen(true)} aria-label={t("Menyu")}>
            <Menu className="h-5 w-5" />
          </Button>
          <img src="/savdo-icon.svg" width="28" height="28" alt="Savdo" className="shrink-0 md:hidden" />
          <div className="flex-1" />
          {can("reports.view") && (
            <NavLink to="/" className="hidden items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted hover:bg-surface-2 sm:flex">
              <BarChart3 className="h-3.5 w-3.5" /> {t("Hisobot")}
            </NavLink>
          )}
          <InstallButton className="hidden sm:inline-flex" />
          <LangSwitcher />
          <Button variant="ghost" size="icon" onClick={cycle} title={t(THEME_LABEL[theme])} aria-label={t(THEME_LABEL[theme])}>
            <ThemeIcon className="h-4 w-4" />
          </Button>
          <NavLink to="/profile" className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-surface-2">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
              {(fullName ?? "?").slice(0, 1).toUpperCase()}
            </span>
            <span className="hidden text-left text-sm leading-tight sm:block">
              <span className="block font-medium">{fullName}</span>
              <span className="block text-xs text-muted">{user?.roles.map((r) => t(r.name)).join(", ")}</span>
            </span>
            <UserCog className="h-4 w-4 text-muted" />
          </NavLink>
          <Button variant="ghost" size="icon" onClick={() => void logout()} title={t("Chiqish")} aria-label={t("Chiqish")}>
            <LogOut className="h-4 w-4" />
          </Button>
        </header>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
        <footer className="border-t border-border bg-surface px-4 py-3 print:hidden">
          <ContactInfo />
        </footer>
      </div>
      <Toaster />
    </div>
  );
}
