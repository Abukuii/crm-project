/**
 * Ko'p tillilik: o'zbekcha (asosiy), ruscha, inglizcha.
 *
 * Kalit — o'zbekcha matnning o'zi: `t("Savdo tarixi")`. Tarjima topilmasa o'zbekcha ko'rsatiladi.
 * O'zgaruvchilar: `t("Savdo #{n} bekor qilindi", { n: 12 })`.
 * Til almashganda marshrutlar qayta chiziladi (main.tsx: `<Routes key={lang}>`).
 */
import { create } from "zustand";

import { en } from "./en";
import { ru } from "./ru";

export type Lang = "uz" | "ru" | "en";

export const LANGS: { code: Lang; label: string; short: string }[] = [
  { code: "uz", label: "O‘zbekcha", short: "UZ" },
  { code: "ru", label: "Русский", short: "RU" },
  { code: "en", label: "English", short: "EN" },
];

const DICTS: Record<Lang, Record<string, string> | null> = { uz: null, ru, en };
const LOCALES: Record<Lang, string> = { uz: "uz-Latn-UZ", ru: "ru-RU", en: "en-GB" };

function detect(): Lang {
  try {
    const saved = localStorage.getItem("lang");
    if (saved === "uz" || saved === "ru" || saved === "en") return saved;
  } catch {
    /* private rejim */
  }
  const nav = (typeof navigator !== "undefined" ? navigator.language : "uz").toLowerCase();
  return nav.startsWith("ru") ? "ru" : nav.startsWith("en") ? "en" : "uz";
}

interface LangState {
  lang: Lang;
  explicit: boolean; // foydalanuvchi o'zi tanlaganmi
  setLang: (lang: Lang) => void;
}

export const useLang = create<LangState>((set) => ({
  lang: detect(),
  explicit: (() => {
    try {
      return !!localStorage.getItem("lang");
    } catch {
      return false;
    }
  })(),
  setLang(lang) {
    try {
      localStorage.setItem("lang", lang);
    } catch {
      /* e'tiborsiz */
    }
    if (typeof document !== "undefined") document.documentElement.lang = lang;
    set({ lang, explicit: true });
  },
}));

if (typeof document !== "undefined") document.documentElement.lang = useLang.getState().lang;

export function t(key: string, vars?: Record<string, string | number | null | undefined>): string {
  const dict = DICTS[useLang.getState().lang];
  let text = dict?.[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) text = text.split(`{${k}}`).join(String(v ?? ""));
  }
  return text;
}

/** Joriy til uchun Intl locale. */
export function locale(): string {
  return LOCALES[useLang.getState().lang];
}

// Ba'zi brauzerlarda Intl o'zbekcha oy/kun nomlarini bilmaydi ("M11", "Mon") — o'zimiz beramiz.
const UZ_WEEKDAYS = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"];
const UZ_WEEKDAYS_SHORT = ["Ya", "Du", "Se", "Ch", "Pa", "Ju", "Sh"];
const UZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];

/** "Dushanba, 23-noyabr" / "понедельник, 23 ноября" / "Monday 23 November". */
export function longDate(d: Date): string {
  if (useLang.getState().lang === "uz") return `${UZ_WEEKDAYS[d.getDay()]}, ${d.getDate()}-${UZ_MONTHS[d.getMonth()]}`;
  return d.toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long" });
}

/** Hafta kunining qisqa nomi: "Du" / "пн" / "Mon". */
export function weekdayShort(d: Date): string {
  if (useLang.getState().lang === "uz") return UZ_WEEKDAYS_SHORT[d.getDay()]!;
  return d.toLocaleDateString(locale(), { weekday: "short" });
}
