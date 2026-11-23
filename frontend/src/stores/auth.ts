import { create } from "zustand";

import type { AuthResponse, Me } from "@/api/types";
import { useLang, type Lang } from "@/i18n";
import { api, refreshAccess, tokenStore } from "@/lib/api";

type Status = "loading" | "authenticated" | "anonymous";

/** Foydalanuvchi bu brauzerda til tanlamagan bo'lsa — profilidagi til qo'llanadi. */
function applyUserLang(user: Me) {
  const { explicit } = useLang.getState();
  const code = user.language as Lang | undefined;
  if (!explicit && code && ["uz", "ru", "en"].includes(code)) useLang.setState({ lang: code });
}

interface AuthState {
  status: Status;
  user: Me | null;
  bootstrap: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (perm: string) => boolean;
}

export const useAuth = create<AuthState>((set, get) => ({
  status: "loading",
  user: null,

  /** Sahifa ochilganda: cookie'dagi refresh orqali sessiyani tiklash. */
  async bootstrap() {
    const token = await refreshAccess();
    if (!token) {
      set({ status: "anonymous", user: null });
      return;
    }
    try {
      const user = await api<Me>("/auth/me/");
      applyUserLang(user);
      set({ status: "authenticated", user });
    } catch {
      tokenStore.set(null);
      set({ status: "anonymous", user: null });
    }
  },

  async login(username, password) {
    const data = await api<AuthResponse>("/auth/login/", {
      method: "POST",
      body: { username, password },
    }, false);
    tokenStore.set(data.access);
    applyUserLang(data.user);
    set({ status: "authenticated", user: data.user });
  },

  async logout() {
    try {
      await api("/auth/logout/", { method: "POST" }, false);
    } finally {
      tokenStore.set(null);
      set({ status: "anonymous", user: null });
    }
  },

  can(perm) {
    return get().user?.permissions.includes(perm) ?? false;
  },
}));

tokenStore.onExpired(() => {
  tokenStore.set(null);
  useAuth.setState({ status: "anonymous", user: null });
});
