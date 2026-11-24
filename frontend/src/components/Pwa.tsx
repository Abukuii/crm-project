/**
 * PWA: ilovani o'rnatish, yangi versiya haqida so'rov va internet holati.
 *
 * Yangilanish avtomatik qo'llanmaydi — kassir savdo o'rtasida sahifa qayta yuklanib
 * ketmasligi uchun foydalanuvchidan so'raladi.
 */
import { Download, RefreshCw, Share, SquarePlus, WifiOff, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useRegisterSW } from "virtual:pwa-register/react";
import { create } from "zustand";

import { Modal } from "@/components/overlay";
import { Button } from "@/components/ui";
import { t } from "@/i18n";
import { cn } from "@/lib/cn";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const ua = typeof navigator === "undefined" ? "" : navigator.userAgent;
/** iPhone va iPad (iPadOS o'zini Mac deb ko'rsatadi) */
export const isIOS =
  /iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && (navigator?.maxTouchPoints ?? 0) > 1);

function standalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.matchMedia("(display-mode: window-controls-overlay)").matches ||
    (navigator as { standalone?: boolean }).standalone === true
  );
}

interface PwaState {
  prompt: BeforeInstallPromptEvent | null;
  installed: boolean;
}

const usePwaStore = create<PwaState>(() => ({ prompt: null, installed: standalone() }));

if (typeof window !== "undefined") {
  // Hodisa React yuklanishidan oldin ham kelishi mumkin — shuning uchun modul darajasida
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    usePwaStore.setState({ prompt: e as BeforeInstallPromptEvent });
  });
  window.addEventListener("appinstalled", () =>
    usePwaStore.setState({ prompt: null, installed: true }),
  );
}

/** "Ilovani o'rnatish" tugmasi. O'rnatilgan bo'lsa yoki imkoni bo'lmasa — ko'rinmaydi. */
export function InstallButton({ className }: { className?: string }) {
  const { prompt, installed } = usePwaStore();
  const [howTo, setHowTo] = useState(false);

  if (installed) return null;
  // iOS'da brauzer so'rov hodisasini bermaydi — qo'lda ko'rsatma beramiz
  if (!prompt && !isIOS) return null;

  const install = async () => {
    if (!prompt) return;
    await prompt.prompt();
    const { outcome } = await prompt.userChoice;
    if (outcome === "accepted") usePwaStore.setState({ prompt: null });
  };

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        className={className}
        onClick={() => (prompt ? void install() : setHowTo(true))}
        title={t("Ilovani o'rnatish")}
      >
        <Download className="h-4 w-4" />
        <span className="hidden sm:inline">{t("Ilovani o'rnatish")}</span>
      </Button>

      <Modal
        open={howTo}
        onClose={() => setHowTo(false)}
        size="sm"
        title={t("Ilovani o'rnatish")}
        footer={<Button onClick={() => setHowTo(false)}>{t("Tushunarli")}</Button>}
      >
        <ol className="space-y-3 text-sm">
          <li className="flex items-start gap-3">
            <Share className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
            <span>{t("Safari pastidagi \"Ulashish\" tugmasini bosing")}</span>
          </li>
          <li className="flex items-start gap-3">
            <SquarePlus className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
            <span>{t("\"Uyga qo'shish\" (Add to Home Screen) ni tanlang")}</span>
          </li>
        </ol>
        <p className="mt-4 rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">
          {t("iPhone'da bildirishnomalar faqat shu tarzda o'rnatilgan ilovada ishlaydi.")}
        </p>
      </Modal>
    </>
  );
}

/** Yangi versiya so'rovi va internet yo'qligi haqida xabar. Ilovada bir marta chiziladi. */
export function PwaPrompts() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      // Soatiga bir marta yangi versiyani tekshirib turamiz (ilova uzoq ochiq tursa ham)
      if (registration) setInterval(() => void registration.update(), 60 * 60 * 1000);
    },
  });
  const [offline, setOffline] = useState(typeof navigator !== "undefined" && !navigator.onLine);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  return (
    <>
      {offline && (
        <div
          className="anim-slide-up fixed inset-x-0 top-0 z-[70] flex items-center justify-center gap-2 bg-warning px-3 py-1.5 text-xs font-medium text-white print:hidden"
          role="status"
        >
          <WifiOff className="h-3.5 w-3.5" />
          {t("Internet yo'q — ma'lumotlar yangilanmayapti")}
        </div>
      )}

      {needRefresh && (
        <div
          className={cn(
            "anim-slide-up fixed bottom-4 left-4 z-[60] w-[min(92vw,360px)] rounded-xl border border-border",
            "bg-surface p-4 shadow-xl print:hidden",
          )}
          role="alert"
        >
          <div className="flex items-start gap-3">
            <RefreshCw className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
            <div className="flex-1">
              <p className="font-medium">{t("Yangi versiya tayyor")}</p>
              <p className="mt-0.5 text-sm text-muted">
                {t("Yangilash uchun ilova qayta yuklanadi.")}
              </p>
            </div>
            <button
              onClick={() => setNeedRefresh(false)}
              className="text-muted hover:text-fg"
              aria-label={t("Yopish")}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setNeedRefresh(false)}>
              {t("Keyinroq")}
            </Button>
            <Button
              size="sm"
              loading={updating}
              onClick={() => {
                setUpdating(true);
                void updateServiceWorker(true);
              }}
            >
              {t("Yangilash")}
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
