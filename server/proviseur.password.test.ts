import { describe, expect, it } from "vitest";

describe.skipIf(process.env.RUN_PROVISEUR_PASSWORD_TEST !== "1")("mot de passe proviseur", () => {
  it("permet une connexion Flask avec le nouveau secret", async () => {
    const password = process.env.LTT_PROVISEUR_NEW_PASSWORD;
    // Le secret n’est jamais imprimé : il est vérifié uniquement par l’API de connexion.
    expect(password?.length ?? 0).toBeGreaterThanOrEqual(12);

    const response = await fetch("http://127.0.0.1:3000/login", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: "proviseur", password }),
      redirect: "manual",
    });

    expect([302, 303]).toContain(response.status);
    expect(response.headers.get("location")).toBeTruthy();
    expect(response.headers.get("set-cookie") ?? "").toContain("session=");
  });
});
