import { describe, expect, it } from "vitest";

import { formatMoney, formatNumber, formatQty } from "./format";

const S = " ";

describe("format", () => {
  it("groups thousands with non-breaking spaces", () => {
    expect(formatNumber(1250000)).toBe(`1${S}250${S}000`);
  });

  it("trims trailing zeros and uses comma", () => {
    expect(formatNumber("2.500")).toBe("2,5");
    expect(formatNumber("10.000")).toBe("10");
  });

  it("handles negatives and empties", () => {
    expect(formatNumber(-1500)).toBe(`−1${S}500`);
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber("abc")).toBe("—");
  });

  it("formats money by currency", () => {
    expect(formatMoney("350000.0000")).toBe(`350${S}000${S}so'm`);
    expect(formatMoney("12.5", "USD")).toBe("$12,5");
  });

  it("formats quantity with unit", () => {
    expect(formatQty("97.500", "m")).toBe(`97,5${S}m`);
  });
});
