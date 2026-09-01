import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(here, "..");

function readProjectFile(relativePath: string) {
  return readFileSync(join(projectRoot, relativePath), "utf8");
}

describe("conseiller orientation schedule access", () => {
  it("allows class schedule viewing endpoints for the counselor role", () => {
    const source = readProjectFile("flask_app/censeur_routes.py");
    expect(source).toContain('@roles_required("censeur", "censeur_crm", "conseiller_orientation", "directeur")');
    expect(source).toContain('is_readonly = user.role in ("censeur_crm", "conseiller_orientation")');
  });

  it("keeps schedule construction unavailable to the counselor", () => {
    const source = readProjectFile("flask_app/censeur_routes.py");
    expect(source).toContain('if user.role not in ("censeur", "directeur") or is_readonly:');
  });

  it("adds a consultation-only menu entry", () => {
    const template = readProjectFile("flask_app/templates/base.html");
    expect(template).toContain("current_user.role == 'conseiller_orientation'");
    expect(template).toContain("Emplois du temps par classe");
    expect(template).toContain("Consultation et impression uniquement");
  });
});
