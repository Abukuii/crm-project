import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // Service worker'ni o'zimiz yozamiz (src/sw.ts) — push bildirishnomalari uchun kerak
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      // Yangi versiya o'zi qayta yuklanmaydi: kassir savdo o'rtasida uzilib qolmasligi uchun
      // foydalanuvchidan so'raladi (components/PwaPrompts.tsx)
      registerType: "prompt",
      injectRegister: null,
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,svg,png,ico,webmanifest}"],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
      // Dev serverda SW keshi chalkashtirmasin
      devOptions: { enabled: false },
      manifest: {
        id: "/",
        name: "Savdo — savdo va ombor boshqaruvi",
        short_name: "Savdo",
        description: "Kassa, ombor, nasiya va hisobotlar bitta tizimda",
        lang: "uz",
        dir: "ltr",
        start_url: "/",
        scope: "/",
        display: "standalone",
        display_override: ["window-controls-overlay", "standalone", "minimal-ui"],
        orientation: "any",
        background_color: "#0b1220",
        theme_color: "#ea580c",
        categories: ["business", "finance", "productivity"],
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
        shortcuts: [
          { name: "Kassa", short_name: "Kassa", url: "/pos" },
          { name: "Savdo tarixi", short_name: "Savdolar", url: "/sales" },
          { name: "Qoldiqlar", short_name: "Qoldiq", url: "/stock" },
        ],
      },
    }),
  ],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  // Ishlab chiqarish buildini lokalda sinash uchun (service worker faqat shu yerda ishlaydi):
  //   npm run build && npm run preview
  preview: {
    port: 4173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "node",
  },
});
