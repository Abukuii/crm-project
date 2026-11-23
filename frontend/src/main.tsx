import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useEffect, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ApiError } from "@/lib/api";
import { CustomersPage } from "@/pages/CustomersPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ExpensesPage } from "@/pages/ExpensesPage";
import { LandingPage } from "@/pages/LandingPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { PosPage } from "@/pages/PosPage";
import { ProductsPage } from "@/pages/ProductsPage";
import { PurchasesPage } from "@/pages/PurchasesPage";
import { RemindersPage } from "@/pages/RemindersPage";
import { SalesPage } from "@/pages/SalesPage";
import { ProfilePage, SettingsPage } from "@/pages/SettingsPage";
import { ShiftsPage } from "@/pages/ShiftsPage";
import { StockPage } from "@/pages/StockPage";
import { SuppliersPage } from "@/pages/SuppliersPage";
import { UsersPage } from "@/pages/UsersPage";
import { useLang } from "@/i18n";
import { useAuth } from "@/stores/auth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

function Spinner() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand border-t-transparent" role="status" aria-label="Yuklanmoqda" />
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const status = useAuth((s) => s.status);
  const location = useLocation();
  if (status === "loading") return <Spinner />;
  if (status === "anonymous") return <Navigate to="/welcome" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

/** Ruxsat bo'lmasa — bosh sahifaga. */
function Perm({ perm, children }: { perm: string; children: ReactNode }) {
  const can = useAuth((s) => s.can);
  return can(perm) ? <>{children}</> : <PlaceholderPage title="Ruxsat yo'q" />;
}

function App() {
  const { bootstrap, status } = useAuth();
  const lang = useLang((s) => s.lang);
  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <Routes key={lang}>
      <Route path="/welcome" element={status === "loading" ? <Spinner /> : <LandingPage />} />
      <Route path="/login" element={<Navigate to="/welcome" replace />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="pos" element={<Perm perm="sales.create"><PosPage /></Perm>} />
        <Route path="shifts" element={<Perm perm="sales.create"><ShiftsPage /></Perm>} />
        <Route path="sales" element={<Perm perm="sales.create"><SalesPage /></Perm>} />
        <Route path="customers" element={<Perm perm="customers.view"><CustomersPage /></Perm>} />
        <Route path="products" element={<Perm perm="catalog.view"><ProductsPage /></Perm>} />
        <Route path="stock" element={<Perm perm="inventory.view"><StockPage /></Perm>} />
        <Route path="purchases" element={<Perm perm="inventory.manage"><PurchasesPage /></Perm>} />
        <Route path="suppliers" element={<Perm perm="inventory.view"><SuppliersPage /></Perm>} />
        <Route path="expenses" element={<Perm perm="expenses.manage"><ExpensesPage /></Perm>} />
        <Route path="reminders" element={<Perm perm="reminders.manage"><RemindersPage /></Perm>} />
        <Route path="users" element={<Perm perm="users.manage"><UsersPage /></Perm>} />
        <Route path="settings" element={<Perm perm="settings.manage"><SettingsPage /></Perm>} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="*" element={<PlaceholderPage title="Sahifa topilmadi" />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
