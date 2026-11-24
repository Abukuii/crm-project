/**
 * PWA ikonkalarini bitta logotipdan generatsiya qiladi (public/icons/).
 *
 * Ishlatish (logotip o'zgarsa):
 *   cd frontend && npm i -D --no-save sharp && node scripts/generate-icons.mjs
 *
 * sharp doimiy bog'liqlik emas — ikonkalar repozitoriyga tayyor holda qo'yiladi,
 * shuning uchun CI va oddiy `npm ci` uchun kerak bo'lmaydi.
 */
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = join(root, "public", "icons");

const GRADIENT = `
  <defs>
    <linearGradient id="g" x2="1" y2="1" gradientUnits="objectBoundingBox">
      <stop stop-color="#ea580c"/>
      <stop offset="1" stop-color="#c2410c"/>
    </linearGradient>
  </defs>`;

/** "S" harfi — savdo_icon.svg dagi bilan bir xil shakl. */
const LETTER = `<path d="M22 9H13a3.5 3.5 0 0 0 0 7h6a3.5 3.5 0 0 1 0 7h-9"
    fill="none" stroke="white" stroke-width="4" stroke-linecap="round"/>`;

/** @param {{radius?: number, scale?: number}} opts */
function logo({ radius = 8, scale = 1 } = {}) {
  const letter =
    scale === 1
      ? LETTER
      : `<g transform="translate(16 16) scale(${scale}) translate(-16 -16)">${LETTER}</g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">${GRADIENT}
  <rect width="32" height="32" rx="${radius}" fill="url(#g)"/>
  ${letter}
</svg>`;
}

/** Bildirishnoma badge'i: Android uni niqob sifatida ishlatadi — faqat oq shakl, fonsiz. */
const badge = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <g transform="translate(16 16) scale(0.8) translate(-16 -16)">${LETTER}</g>
</svg>`;

const icons = [
  // Oddiy ikonkalar (purpose: any) — burchaklari yumaloq
  { file: "icon-192.png", size: 192, svg: logo() },
  { file: "icon-512.png", size: 512, svg: logo() },
  // Maskable — fon chetgacha to'ladi, logotip xavfsiz zonada (Android uni kesadi)
  { file: "maskable-512.png", size: 512, svg: logo({ radius: 0, scale: 0.78 }) },
  // iOS: shaffoflik qora bo'lib ko'rinadi, burchaklarni iOS o'zi yumaloqlaydi
  { file: "apple-touch-icon.png", size: 180, svg: logo({ radius: 0, scale: 0.86 }) },
  // Bildirishnoma status qatorida (Android)
  { file: "badge-96.png", size: 96, svg: badge },
];

await mkdir(outDir, { recursive: true });
for (const { file, size, svg } of icons) {
  const png = await sharp(Buffer.from(svg)).resize(size, size).png({ compressionLevel: 9 }).toBuffer();
  await writeFile(join(outDir, file), png);
  console.log(`${file.padEnd(22)} ${size}x${size}  ${(png.length / 1024).toFixed(1)} KB`);
}
