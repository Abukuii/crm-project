import { create } from "zustand";

export type Theme = "system" | "light" | "dark";

function read(): Theme {
  try {
    const v = localStorage.getItem("theme");
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function apply(theme: Theme) {
  const dark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  cycle: () => void;
}

export const useTheme = create<ThemeState>((set, get) => ({
  theme: read(),
  setTheme(theme) {
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* private rejim — e'tiborsiz */
    }
    apply(theme);
    set({ theme });
  },
  cycle() {
    const order: Theme[] = ["system", "light", "dark"];
    const next = order[(order.indexOf(get().theme) + 1) % order.length] ?? "system";
    get().setTheme(next);
  },
}));

window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", () => apply(useTheme.getState().theme));
