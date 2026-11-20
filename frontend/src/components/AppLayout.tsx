import {
  BarChart3,
  Boxes,
  ChevronsLeft,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Package,
  Settings,
  ShoppingCart,
  Sun,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  perm?: string;
  soon?: boolean;
}

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Asosiy",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard },
      { to: "/pos", label: "Kassa", icon: ShoppingCart, perm: "sales.create", soon: true },
    ],
  },
  {
    group: "Ombor",
    items: [
      { to: "/products", label: "Mahsulotlar", icon: Package, perm: "catalog.view" },
      { to: "/stock", label: "Qoldiqlar", icon: Boxes, perm: "inventory.view" },
      { to: "/purchases", label: "Kirim", icon: Truck, perm: "inventory.manage", soon: true },
    ],
  },
  {
    group: "Boshqaruv",
    items: [
      { to: "/customers", label: "Mijozlar", icon: Users, perm: "customers.view", soon: true },
      { to: "/finance", label: "Moliya", icon: Wallet, perm: "finance.view", soon: true },
      { to: "/reports", label: "Hisobotlar", icon: BarChart3, perm: "reports.view", soon: true },
      { to: "/settings", label: "Sozlamalar", icon: Settings, perm: "settings.manage", soon: true },
    ],
  },
];

const THEME_ICON = { system: Monitor, light: Sun, dark: Moon } as const;
const THEME_LABEL = { system: "Tizim mavzusi", light: "Yorug' mavzu", dark: "Tun mavzusi" } as const;

export function AppLayout() {
  const { user, logout, can } = useAuth();
  const { theme, cycle } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const ThemeIcon = THEME_ICON[theme];

  const sidebar = (
    <nav className="flex h-full flex-col gap-6 overflow-y-auto p-3" aria-label="Asosiy menyu">
      {NAV.map(({ group, items }) => {
        const visible = items.filter((i) => !i.perm || can(i.perm));
        if (!visible.length) return null;
        return (
          <div key={group} className="space-y-1">
            {!collapsed && (
              <p className="px-3 text-xs font-semibold uppercase tracking-wide text-muted">{group}</p>
            )}
            {visible.map(({ to, label, icon: Icon, soon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                onClick={() => setMobileOpen(false)}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                    isActive ? "bg-brand-soft text-brand" : "text-muted hover:bg-surface-2 hover:text-fg",
                    collapsed && "justify-center px-0",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                {!collapsed && <span className="flex-1 truncate">{label}</span>}
                {!collapsed && soon && <span className="text-[10px] text-muted">tez orada</span>}
              </NavLink>
            ))}
          </div>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-dvh">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-surface md:flex",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <div className="flex h-14 items-center gap-2 border-b border-border px-4">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand font-bold text-on-brand">Q</div>
          {!collapsed && <span className="truncate font-semibold">{user?.tenant?.name ?? "Qurilish CRM"}</span>}
        </div>
        <div className="flex-1">{sidebar}</div>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="flex h-10 items-center justify-center border-t border-border text-muted hover:text-fg"
          aria-label={collapsed ? "Menyuni ochish" : "Menyuni yig'ish"}
        >
          <ChevronsLeft className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />
        </button>
      </aside>

      {/* Mobil sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal>
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-surface shadow-xl">{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-surface/80 px-4 backdrop-blur">
          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileOpen(true)} aria-label="Menyu">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="flex-1" />
          <Button variant="ghost" size="icon" onClick={cycle} title={THEME_LABEL[theme]} aria-label={THEME_LABEL[theme]}>
            <ThemeIcon className="h-4 w-4" />
          </Button>
          <div className="hidden text-right text-sm leading-tight sm:block">
            <p className="font-medium">{[user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username}</p>
            <p className="text-xs text-muted">{user?.roles.map((r) => r.name).join(", ")}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={() => void logout()} title="Chiqish" aria-label="Chiqish">
            <LogOut className="h-4 w-4" />
          </Button>
        </header>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
