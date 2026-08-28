import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("documents imprimés", () => {
  it("masque le badge Made with Manus uniquement dans le média print", () => {
    const template = readFileSync("flask_app/templates/base.html", "utf8");

    expect(template).toContain("@media print");
    expect(template).toContain('[data-ltt-print-excluded="external-branding"]');
    expect(template).toContain('a[href*="manus.im"]');
    expect(template).toContain("markExternalPrintBranding");
    expect(template).toContain("beforeprint");
    expect(template).toContain("MutationObserver");
  });
});
