import { describe, expect, it } from "vitest";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

function templatePath(relativePath: string) {
  return fileURLToPath(new URL(`../flask_app/${relativePath}`, import.meta.url));
}

function assertOrder(template: string, firstLabel: string, secondLabel: string) {
  const first = template.indexOf(firstLabel);
  const second = template.indexOf(secondLabel);
  expect(first).toBeGreaterThanOrEqual(0);
  expect(second).toBeGreaterThanOrEqual(0);
  expect(first).toBeLessThan(second);
}

describe("bulletin summary indicator order", () => {
  it("shows the requested order on the screen bulletin", () => {
    const template = readFileSync(templatePath("templates/bulletin.html"), "utf8");
    assertOrder(template, "TRAVAIL DE L’ÉLÈVE", "Total des points");
    assertOrder(template, "Total des points", "Moyenne classe");
    assertOrder(template, "Moyenne trimestrielle", "Moyenne du dernier");
    assertOrder(template, "Rang", "Moyennes ≥ 10");
    assertOrder(template, "Éval.{{ data.term_seq_a }}", "Taux de Réussite");
    assertOrder(template, "Éval.{{ data.term_seq_a }}", "Éval.{{ data.term_seq_b }}");
  });

  it("shows the requested order in the quarterly PDF", () => {
    const template = readFileSync(templatePath("templates/pdf/_bulletin_body.html"), "utf8");
    assertOrder(template, "TRAVAIL DE L’ÉLÈVE", "Total des points");
    assertOrder(template, "Total des points", "Moyenne classe");
    assertOrder(template, "Moyenne trimestrielle", "Moyenne du dernier");
    assertOrder(template, "Rang", "Moyennes ≥ 10");
    assertOrder(template, "Éval.{{ data.term_seq_a }}", "Taux réussite");
    assertOrder(template, "Éval.{{ data.term_seq_a }}", "Éval.{{ data.term_seq_b }}");
  });

  it("keeps total points before the class average in annual summaries", () => {
    const templates = [
      readFileSync(templatePath("templates/pdf/bulletin_annual_pdf.html"), "utf8"),
      readFileSync(templatePath("templates/pdf/class_annual_bulletins_pdf.html"), "utf8"),
    ];
    for (const template of templates) {
      assertOrder(template, "Total Points", "Moy. Gén. Classe");
    }
  });
});
