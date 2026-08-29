import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("filtre Filière du module Bulletins", () => {
  it("relie le filtre serveur et la liste dynamique des classes", () => {
    const route = readFileSync("flask_app/censeur_routes.py", "utf8");
    const template = readFileSync("flask_app/templates/censeur_bulletins.html", "utf8");

    expect(route).toContain('department_id = request.args.get("department_id", type=int)');
    expect(route).toContain("selected_class.department_id != department_id");
    expect(route).toContain("classes_by_department");
    expect(template).toContain('name="department_id"');
    expect(template).toContain('id="bulletinClassFilter"');
    expect(template).toContain("classesByDepartment[departmentSelect.value]");
    expect(template).toContain("classSelect.replaceChildren");
  });
});
