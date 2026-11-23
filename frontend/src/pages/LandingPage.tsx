import {
  ArrowRight,
  BarChart3,
  Bell,
  Boxes,
  FileSpreadsheet,
  HandCoins,
  KeyRound,
  Moon,
  ScanBarcode,
  ShieldCheck,
  ShoppingCart,
  Sun,
  TrendingUp,
  User,
  Wallet,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { t, weekdayShort } from "@/i18n";
import { LangSwitcher } from "@/components/LangSwitcher";
import { Button, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";

/* ── Kichik yordamchilar ─────────────────────────────────────────────────── */

/** Ekranga chiqqanda 0 dan qiymatgacha sanaydi. */
function CountUp({ to, suffix = "", duration = 1600 }: { to: number; suffix?: string; duration?: number }) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const obs = new IntersectionObserver(([entry]) => {
      if (!entry?.isIntersecting) return;
      obs.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const p = Math.min(1, (now - start) / duration);
        setValue(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    });
    obs.observe(el);
    return () => {
      obs.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [to, duration]);
  return (
    <span ref={ref} className="num">
      {value.toLocaleString("ru-RU").replace(/,/g, " ")}
      {suffix}
    </span>
  );
}

/** Scroll qilinganda paydo bo'luvchi blok. */
function Reveal({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => e?.isIntersecting && (setShown(true), obs.disconnect()), {
      threshold: 0.15,
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={cn(
        "transition-all duration-700 ease-out",
        shown ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

/* ── Animatsiyali "jonli" dashboard maketi ───────────────────────────────── */

const BARS = [42, 58, 49, 71, 64, 88, 79];
/** Dushanbadan boshlab hafta kunlari (joriy til bo'yicha qisqa nomlar). */
const weekdays = () =>
  Array.from({ length: 7 }, (_, i) => weekdayShort(new Date(2024, 0, 1 + i)).slice(0, 2));

function DashboardMockup() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 2600);
    return () => clearInterval(id);
  }, []);
  const feed = [
    { who: "Usta Botir", what: "Sement M-400 × 20 qop", sum: "1 160 000", tone: "text-warning", tag: "Nasiya" },
    { who: "Naqd mijoz", what: "Armatura 12 mm × 120 m", sum: "1 740 000", tone: "text-success", tag: "Naqd" },
    { who: "Qurilish LLC", what: "Kabel VVG × 3 rulon", sum: "3 000 000", tone: "text-brand", tag: "Karta" },
  ];
  const current = feed[tick % feed.length]!;
  const DAYS = weekdays();

  return (
    <div className="relative">
      {/* Asosiy karta */}
      <div className="anim-float rounded-2xl border border-white/10 bg-slate-900/80 p-5 text-slate-100 shadow-2xl shadow-orange-500/10 backdrop-blur-xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
          </div>
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="relative flex h-2 w-2">
              <span className="anim-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            {t("Jonli")}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Bugungi savdo", value: "18,4 mln", delta: "+12%" },
            { label: "Sof foyda", value: "3,2 mln", delta: "+8%" },
            { label: "Cheklar", value: "47", delta: "+5" },
          ].map((k, i) => (
            <div key={k.label} className="anim-slide-up rounded-xl bg-white/5 p-3" style={{ animationDelay: `${300 + i * 120}ms` }}>
              <p className="text-[11px] text-slate-400">{t(k.label)}</p>
              <p className="mt-1 text-lg font-semibold num">{k.value}</p>
              <p className="text-[11px] text-emerald-400">{k.delta}</p>
            </div>
          ))}
        </div>

        <div className="mt-4 rounded-xl bg-white/5 p-3">
          <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
            <span>{t("Haftalik savdo")}</span>
            <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <div className="relative flex h-28 items-end gap-2">
            {BARS.map((h, i) => (
              <div key={DAYS[i]} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className="anim-bar w-full rounded-t-md bg-gradient-to-t from-orange-600 to-amber-400"
                  style={{ height: `${h}%`, animationDelay: `${500 + i * 90}ms` }}
                />
                <span className="text-[10px] text-slate-500">{DAYS[i]}</span>
              </div>
            ))}
            <svg className="pointer-events-none absolute inset-x-0 top-0 h-[calc(100%-16px)] w-full" viewBox="0 0 300 100" preserveAspectRatio="none">
              <polyline
                className="anim-draw"
                points="20,62 63,45 106,54 149,30 192,38 235,12 278,22"
                fill="none"
                stroke="#fde68a"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ animationDelay: "900ms" }}
              />
            </svg>
          </div>
        </div>

        <div key={tick} className="anim-slide-up mt-4 flex items-center gap-3 rounded-xl bg-white/5 p-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-orange-500/15 text-orange-400">
            <ShoppingCart className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{t(current.who)}</p>
            <p className="truncate text-xs text-slate-400">{current.what}</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold num">{current.sum}</p>
            <p className={cn("text-[11px]", current.tone)}>{t(current.tag)}</p>
          </div>
        </div>
      </div>

      {/* Suzib yuruvchi kartochkalar */}
      <div className="anim-float absolute -left-6 -top-6 hidden rounded-xl border border-white/10 bg-slate-900/90 px-3 py-2 text-xs text-slate-200 shadow-xl backdrop-blur sm:flex sm:items-center sm:gap-2" style={{ animationDelay: "-2s" }}>
        <ScanBarcode className="h-4 w-4 text-orange-400" /> {t("Shtrix-kod: 0,3 s")}
      </div>
      <div className="anim-float absolute -bottom-5 -right-4 hidden rounded-xl border border-white/10 bg-slate-900/90 px-3 py-2 text-xs text-slate-200 shadow-xl backdrop-blur sm:flex sm:items-center sm:gap-2" style={{ animationDelay: "-4s" }}>
        <Bell className="h-4 w-4 text-amber-400" /> {t("Telegram: yangi savdo")}
      </div>
    </div>
  );
}

/* ── Kirish formasi ──────────────────────────────────────────────────────── */

function LoginCard() {
  const login = useAuth((s) => s.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof ApiError ? t(err.message) : t("Kutilmagan xatolik"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div id="login" className="anim-pop relative rounded-3xl border border-border bg-surface/90 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
      <div className="pointer-events-none absolute -inset-px -z-10 rounded-3xl bg-gradient-to-br from-orange-500/40 via-transparent to-amber-400/30 blur-sm" />
      <div className="mb-6">
        <h2 className="text-xl font-semibold">{t("Hisobingizga kiring")}</h2>
        <p className="mt-1 text-sm text-muted">{t("Kassa, ombor va hisobotlar — bitta joyda")}</p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input
          label={t("Login")}
          name="username"
          autoComplete="username"
          required
          icon={<User className="h-4 w-4" />}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <Input
          label={t("Parol")}
          name="password"
          type="password"
          autoComplete="current-password"
          required
          icon={<KeyRound className="h-4 w-4" />}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="anim-pop rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        <Button type="submit" className="h-11 w-full text-base" loading={loading} disabled={!username || !password}>
          {t("Kirish")} <ArrowRight className="h-4 w-4" />
        </Button>
      </form>
      <div className="mt-6 flex items-center gap-2 text-xs text-muted">
        <ShieldCheck className="h-4 w-4 text-success" />
        {t("Ma'lumotlar shifrlangan aloqa orqali uzatiladi")}
      </div>
    </div>
  );
}

/* ── Sahifa ──────────────────────────────────────────────────────────────── */

const FEATURES: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: ShoppingCart, title: "Tezkor kassa", text: "Shtrix-kod, kelishilgan narx, naqd + karta + nasiya bitta chekda." },
  { icon: Boxes, title: "Aniq ombor", text: "Har bir harakat jurnalda. O'rtacha tannarx avtomatik hisoblanadi." },
  { icon: HandCoins, title: "Nasiya nazorati", text: "Kredit limiti, to'lov muddati, muddati o'tgan qarzlar ro'yxati." },
  { icon: BarChart3, title: "Haqiqiy foyda", text: "Aylanma emas — tannarx va xarajatlar ayrilgan sof foyda." },
  { icon: FileSpreadsheet, title: "Excel import", text: "Minglab mahsulotni bir faylda yuklang, xatolar oldindan ko'rsatiladi." },
  { icon: Bell, title: "Telegram xabarlar", text: "Har bir savdo va kunlik hisobot to'g'ridan-to'g'ri telefoningizga." },
];

export function LandingPage() {
  const status = useAuth((s) => s.status);
  const location = useLocation();
  const { theme, cycle } = useTheme();

  if (status === "authenticated") {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  return (
    <div className="relative min-h-dvh overflow-hidden bg-bg">
      {/* Fon: gradient "blob"lar va to'r */}
      <div className="pointer-events-none absolute inset-0 -z-0">
        <div className="anim-blob absolute -left-32 -top-32 h-[28rem] w-[28rem] rounded-full bg-orange-500/25 blur-3xl" />
        <div className="anim-blob absolute -right-24 top-40 h-[24rem] w-[24rem] rounded-full bg-amber-400/20 blur-3xl" style={{ animationDelay: "-5s" }} />
        <div className="anim-blob absolute bottom-0 left-1/3 h-[22rem] w-[22rem] rounded-full bg-rose-500/10 blur-3xl" style={{ animationDelay: "-10s" }} />
        <div
          className="absolute inset-0 opacity-[0.035] dark:opacity-[0.07]"
          style={{
            backgroundImage:
              "linear-gradient(currentColor 1px, transparent 1px), linear-gradient(90deg, currentColor 1px, transparent 1px)",
            backgroundSize: "44px 44px",
          }}
        />
      </div>

      {/* Yuqori panel */}
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 text-lg font-bold text-white shadow-lg shadow-orange-500/30">
            S
          </div>
          <span className="text-lg font-semibold tracking-tight">Savdo</span>
        </div>
        <div className="flex items-center gap-2">
          <LangSwitcher />
          <button onClick={cycle} className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg" aria-label={t("Mavzuni almashtirish")}>
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <a href="#login" className="rounded-lg px-3 py-2 text-sm font-medium text-brand hover:bg-brand-soft lg:hidden">
            {t("Kirish")}
          </a>
        </div>
      </header>

      {/* Hero + login */}
      <main className="relative z-10 mx-auto grid max-w-7xl gap-10 px-4 pb-16 pt-4 sm:px-6 lg:grid-cols-[1fr_400px] lg:gap-14 lg:pt-10">
        <section className="min-w-0">
          <div className="anim-slide-up inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted backdrop-blur">
            <Zap className="h-3.5 w-3.5 text-brand" /> {t("Do'koningiz uchun zamonaviy boshqaruv tizimi")}
          </div>
          <h1 className="anim-slide-up mt-5 text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl" style={{ animationDelay: "80ms" }}>
            {t("Savdoni")} <span className="text-shimmer">{t("aqlli")}</span> {t("boshqaring —")}<br className="hidden sm:block" /> {t("kassadan foydagacha")}
          </h1>
          <p className="anim-slide-up mt-5 max-w-xl text-base text-muted sm:text-lg" style={{ animationDelay: "160ms" }}>
            {t("Sotuv, ombor, nasiya, xarajat va hisobotlar bitta tizimda. Real vaqtdagi raqamlar, haqiqiy foyda va har bir savdo haqida Telegram xabari.")}
          </p>

          <div className="anim-slide-up mt-8 grid max-w-lg grid-cols-3 gap-4" style={{ animationDelay: "240ms" }}>
            {[
              { to: 20, suffix: " s", label: "bitta chek" },
              { to: 100, suffix: "%", label: "aniq qoldiq" },
              { to: 24, suffix: "/7", label: "bulutda" },
            ].map((s) => (
              <div key={s.label}>
                <p className="text-2xl font-bold sm:text-3xl">
                  <CountUp to={s.to} suffix={s.suffix} />
                </p>
                <p className="text-xs text-muted sm:text-sm">{t(s.label)}</p>
              </div>
            ))}
          </div>

          <div className="mt-12 lg:mt-14">
            <DashboardMockup />
          </div>
        </section>

        <aside className="lg:sticky lg:top-8 lg:self-start">
          <LoginCard />
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="anim-slide-up rounded-2xl border border-border bg-surface/70 p-4 backdrop-blur" style={{ animationDelay: "400ms" }}>
              <Wallet className="h-5 w-5 text-brand" />
              <p className="mt-2 text-sm font-medium">{t("Dollar va so'm")}</p>
              <p className="text-xs text-muted">{t("Markaziy bank kursi har kuni")}</p>
            </div>
            <div className="anim-slide-up rounded-2xl border border-border bg-surface/70 p-4 backdrop-blur" style={{ animationDelay: "500ms" }}>
              <ShieldCheck className="h-5 w-5 text-success" />
              <p className="mt-2 text-sm font-medium">{t("Rollar va audit")}</p>
              <p className="text-xs text-muted">{t("Kim nima qilgani yoziladi")}</p>
            </div>
          </div>
        </aside>
      </main>

      {/* Imkoniyatlar */}
      <section className="relative z-10 border-t border-border/60 bg-surface/40 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <Reveal>
            <h2 className="text-center text-3xl font-bold tracking-tight">{t("Do'kon uchun kerak bo'lgan hamma narsa")}</h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-muted">
              {t("Qog'oz daftar va Excel jadvallardan voz keching — Savdo har bir so'mni hisobga oladi.")}
            </p>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 80}>
                <div className="group h-full rounded-2xl border border-border bg-surface p-5 transition-all duration-300 hover:-translate-y-1 hover:border-brand/50 hover:shadow-xl hover:shadow-orange-500/5">
                  <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-soft text-brand transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3">
                    <f.icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 font-semibold">{t(f.title)}</h3>
                  <p className="mt-1 text-sm text-muted">{t(f.text)}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-border/60 py-6 text-center text-xs text-muted">
        © {new Date().getFullYear()} Savdo — {t("savdo va ombor boshqaruv tizimi")}
      </footer>
    </div>
  );
}
