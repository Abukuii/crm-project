import { Phone, Send } from "lucide-react";

import { t } from "@/i18n";

export function ContactInfo() {
  return (
    <address className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-sm not-italic">
      <span className="text-muted">{t("Bog‘lanish uchun")} · <strong className="font-semibold text-fg">Nematov Otabek</strong></span>
      <a href="https://t.me/jasurovich_O" target="_blank" rel="noopener noreferrer"
         className="inline-flex items-center gap-1.5 py-1 text-brand hover:underline">
        <Send size={15} aria-hidden="true" /><span className="sr-only">Telegram </span>@jasurovich_O
      </a>
      <a href="tel:+998990313060" className="inline-flex items-center gap-1.5 whitespace-nowrap py-1 text-brand hover:underline">
        <Phone size={15} aria-hidden="true" /><span className="sr-only">{t("Telefon")} </span>+998 99 031 30 60
      </a>
    </address>
  );
}
