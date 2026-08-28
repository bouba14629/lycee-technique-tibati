import { describe, expect, it } from "vitest";

describe("Flask health endpoint", () => {
  it("répond après le démarrage avec le secret administrateur configuré", async () => {
    expect(process.env.LTT_INITIAL_ADMIN_PASSWORD?.length ?? 0).toBeGreaterThanOrEqual(12);

    const response = await fetch("http://127.0.0.1:5053/health");
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ status: "ok" });
  });
});
