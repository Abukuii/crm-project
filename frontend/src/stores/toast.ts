import { create } from "zustand";

import { ApiError } from "@/lib/api";

export interface Toast {
  id: number;
  tone: "success" | "error" | "info";
  text: string;
}

interface ToastState {
  items: Toast[];
  push: (tone: Toast["tone"], text: string) => void;
  dismiss: (id: number) => void;
}

let seq = 0;

export const useToasts = create<ToastState>((set) => ({
  items: [],
  push(tone, text) {
    const id = ++seq;
    set((s) => ({ items: [...s.items.slice(-3), { id, tone, text }] }));
    setTimeout(() => set((s) => ({ items: s.items.filter((t) => t.id !== id) })), tone === "error" ? 6000 : 3500);
  },
  dismiss(id) {
    set((s) => ({ items: s.items.filter((t) => t.id !== id) }));
  },
}));

export const toast = {
  success: (text: string) => useToasts.getState().push("success", text),
  info: (text: string) => useToasts.getState().push("info", text),
  error: (err: unknown) =>
    useToasts.getState().push("error", err instanceof ApiError ? err.message : String((err as Error)?.message ?? err)),
};
