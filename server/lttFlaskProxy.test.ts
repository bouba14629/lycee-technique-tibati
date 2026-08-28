import { describe, expect, it } from "vitest";
import { getFlaskPort, isFlaskGatewayEnabled, shouldProxyToFlask } from "./lttFlaskProxy";

describe("routage de la passerelle Flask", () => {
  it("réserve les routes système WebDev et délègue les parcours scolaires à Flask", () => {
    expect(shouldProxyToFlask("/login")).toBe(true);
    expect(shouldProxyToFlask("/dashboard")).toBe(true);
    expect(shouldProxyToFlask("/health")).toBe(true);
    expect(shouldProxyToFlask("/api/ltt/health")).toBe(false);
    expect(shouldProxyToFlask("/api/trpc/auth.me")).toBe(false);
    expect(shouldProxyToFlask("/manus-storage/logo.svg")).toBe(false);
  });

  it("active la passerelle par défaut et permet une désactivation explicite", () => {
    expect(isFlaskGatewayEnabled({})).toBe(true);
    expect(isFlaskGatewayEnabled({ LTT_FLASK_ENABLED: "1" })).toBe(true);
    expect(isFlaskGatewayEnabled({ LTT_FLASK_ENABLED: "0" })).toBe(false);
  });

  it("démarre une nouvelle passerelle sur le port 5053 par défaut", () => {
    expect(getFlaskPort({})).toBe(5053);
    expect(getFlaskPort({ LTT_FLASK_PORT: "5051" })).toBe(5051);
    expect(getFlaskPort({ LTT_FLASK_PORT: "invalide" })).toBe(5053);
  });
});
