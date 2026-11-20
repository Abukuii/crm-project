import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useEffect, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ApiError } from "@/lib/api";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { ProductsPage } from "@/pages/ProductsPage";
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

function RequireAuth({ children }: { children: ReactNode }) {
  const status = useAuth((s) => s.status);
  const location = useLocation();
  if (status === "loading") {
    return (
      <div className="grid min-h-dvh place-items-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand border-t-transparent" role="status" aria-label="Yuklanmoqda" />
      </div>
    );
  }
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function App() {
  const bootstrap = useAuth((s) => s.bootstrap);
  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="stock" element={<PlaceholderPage title="Qoldiqlar" />} />
        <Route path="pos" element={<PlaceholderPage title="Kassa" />} />
        <Route path="purchases" element={<PlaceholderPage title="Kirim" />} />
        <Route path="customers" element={<PlaceholderPage title="Mijozlar" />} />
        <Route path="finance" element={<PlaceholderPage title="Moliya" />} />
        <Route path="reports" element={<PlaceholderPage title="Hisobotlar" />} />
        <Route path="settings" element={<PlaceholderPage title="Sozlamalar" />} />
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
