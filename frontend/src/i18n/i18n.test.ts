import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { en } from "./en";
import { ru } from "./ru";
import { t, useLang } from "./index";

/** src ichidagi barcha t("...") kalitlari. */
function collectKeys(dir: string, acc = new Set<string>()): Set<string> {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      if (name !== "i18n") collectKeys(path, acc);
    } else if (/\.tsx?$/.test(name) && !name.endsWith(".test.ts")) {
      const src = readFileSync(path, "utf8");
      for (const m of src.matchAll(/\bt\(\s*"((?:\\.|[^"\\])*)"/g)) acc.add(m[1]!.replace(/\\"/g, '"'));
    }
  }
  return acc;
}

describe("i18n", () => {
  const keys = [...collectKeys(join(__dirname, ".."))];

  it.each([
    ["ru", ru],
    ["en", en],
  ])("%s lug'atida barcha kalitlar bor", (_, dict) => {
    expect(keys.filter((k) => !(k in dict))).toEqual([]);
  });

  it("placeholderlar tarjimada saqlanadi", () => {
    for (const dict of [ru, en]) {
      for (const [key, value] of Object.entries(dict)) {
        const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
        expect(vars(value), key).toBe(vars(key));
      }
    }
  });

  it("til almashganda tarjima qaytaradi", () => {
    useLang.setState({ lang: "ru" });
    expect(t("Savdo #{n} bekor qilindi", { n: 7 })).toBe("Продажа №7 отменена");
    useLang.setState({ lang: "en" });
    expect(t("Kassa")).toBe("Checkout");
    useLang.setState({ lang: "uz" });
    expect(t("Kassa")).toBe("Kassa");
    expect(t("Lug'atda yo'q matn")).toBe("Lug'atda yo'q matn");
  });
});
