import { create } from "zustand";

import type { AuthResponse, Me } from "@/api/types";
import { api, refreshAccess, tokenStore } from "@/lib/api";

type Status = "loading" | "authenticated" | "anonymous";

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
