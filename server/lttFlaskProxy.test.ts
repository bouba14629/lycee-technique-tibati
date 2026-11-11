import { describe, expect, it } from "vitest";
import { getFlaskEnvironment, getFlaskPort, isFlaskGatewayEnabled, shouldProxyToFlask } from "./lttFlaskProxy";

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

  it("récupère les photos depuis Node et jamais depuis le worker Flask unique", () => {
    const environment = getFlaskEnvironment({ PORT: "3007", LTT_FLASK_PORT: "5058", NODE_ENV: "production" });
    expect(environment.LTT_PORT).toBe("5058");
    expect(environment.LTT_STORAGE_BASE_URL).toBe("http://127.0.0.1:3007");
    expect(environment.LTT_ENV).toBe("production");
    expect(getFlaskEnvironment({}).LTT_STORAGE_BASE_URL).toBe("http://127.0.0.1:3000");
  });

  it("préserve une adresse explicite de stockage sur un autre hébergement", () => {
    expect(getFlaskEnvironment({ LTT_STORAGE_BASE_URL: "https://storage.example", LTT_ENV: "development" }).LTT_STORAGE_BASE_URL).toBe("https://storage.example");
  });
});
