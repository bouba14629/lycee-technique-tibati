import type { Express, RequestHandler } from "express";
import express from "express";
import { spawn, type ChildProcess } from "child_process";
import crypto from "crypto";
import http from "http";
import { storagePut } from "./storage";

const PHOTO_EXTENSIONS = new Map([
  ["jpg", "image/jpeg"],
  ["jpeg", "image/jpeg"],
  ["png", "image/png"],
  ["webp", "image/webp"],
]);

export function registerLttMediaUpload(app: Express) {
  app.post("/api/ltt/media", express.raw({ type: "application/octet-stream", limit: "16mb" }), async (req, res) => {
    const expectedToken = process.env.JWT_SECRET || "";
    const suppliedToken = req.header("X-LTT-Internal-Token") || "";
    if (!expectedToken || suppliedToken !== expectedToken) {
      res.status(401).json({ error: "Unauthorized" });
      return;
    }
    const originalName = (req.header("X-File-Name") || "photo.jpg").trim();
    const extension = originalName.split(".").pop()?.toLowerCase() || "";
    const contentType = PHOTO_EXTENSIONS.get(extension);
    const requestedType = req.header("X-File-Type") || contentType;
    if (!contentType || requestedType !== contentType || !Buffer.isBuffer(req.body) || req.body.length === 0) {
      res.status(400).json({ error: "Invalid image upload" });
      return;
    }
    try {
      const safeName = `students/${Date.now()}-${crypto.randomBytes(8).toString("hex")}.${extension}`;
      const stored = await storagePut(safeName, req.body, contentType);
      res.status(201).json({ key: stored.key, url: stored.url });
    } catch (error) {
      console.error("Student photo upload failed", error);
      res.status(502).json({ error: "Photo storage unavailable" });
    }
  });
}


export function getFlaskPort(environment: NodeJS.ProcessEnv = process.env) {
  const configuredPort = Number.parseInt(environment.LTT_FLASK_PORT || "5053", 10);
  return Number.isFinite(configuredPort) ? configuredPort : 5053;
}

const flaskPort = getFlaskPort();
let flaskProcess: ChildProcess | undefined;

export function isFlaskGatewayEnabled(environment: NodeJS.ProcessEnv = process.env) {
  // Le rendu publié repose sur l'interface Flask. React ne devient le point
  // d'entrée que lorsqu'une désactivation explicite est demandée.
  return environment.LTT_FLASK_ENABLED !== "0";
}

export function shouldProxyToFlask(path: string) {
  return !path.startsWith("/api/") && !path.startsWith("/manus-storage/");
}

function waitForFlask(): Promise<void> {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const probe = () => {
      const request = http.get({ hostname: "127.0.0.1", port: flaskPort, path: "/health", timeout: 1000 }, response => {
        response.resume();
        if (response.statusCode === 200) return resolve();
        if (++attempts >= 30) return reject(new Error("Flask health check returned an unexpected status"));
        setTimeout(probe, 500);
      });
      request.on("error", () => {
        if (++attempts >= 30) return reject(new Error("Flask did not become available"));
        setTimeout(probe, 500);
      });
      request.on("timeout", () => request.destroy());
    };
    probe();
  });
}

export async function startFlask() {
  if (flaskProcess) return;
  const python = process.env.LTT_PYTHON_BIN || "python3";
  const environment = {
    ...process.env,
    LTT_HOST: "127.0.0.1",
    LTT_PORT: String(flaskPort),
  };
  const child = spawn(python, ["-m", "gunicorn", "--workers", "1", "--timeout", "120", "--bind", `127.0.0.1:${flaskPort}`, "wsgi:app"], {
    cwd: new URL("../flask_app/", import.meta.url),
    env: environment,
    // Ne pas relayer la sortie de Gunicorn : ses URLs internes pourraient
    // être détectées comme URL de prévisualisation à la place du serveur Node.
    stdio: ["ignore", "ignore", "ignore"],
  });
  flaskProcess = child;
  child.once("exit", code => {
    flaskProcess = undefined;
    console.error(`Flask exited with code ${code ?? "unknown"}`);
  });
  await waitForFlask();
}

export function createFlaskProxy(): RequestHandler {
  return (req, res, next) => {
    if (!shouldProxyToFlask(req.path)) return next();
    const upstream = http.request({
      hostname: "127.0.0.1",
      port: flaskPort,
      method: req.method,
      path: req.originalUrl,
      headers: { ...req.headers, host: `127.0.0.1:${flaskPort}` },
    }, upstreamResponse => {
      res.status(upstreamResponse.statusCode || 502);
      Object.entries(upstreamResponse.headers).forEach(([name, value]) => {
        if (value !== undefined) res.setHeader(name, value);
      });
      upstreamResponse.pipe(res);
    });
    upstream.on("error", error => {
      if (!res.headersSent) res.status(502).json({ error: "Service scolaire temporairement indisponible" });
      else res.destroy(error);
    });
    req.pipe(upstream);
  };
}

export function stopFlask() {
  flaskProcess?.kill("SIGTERM");
}

export async function configureFlaskGateway(app: Express) {
  if (!isFlaskGatewayEnabled()) return false;
  await startFlask();
  app.use(createFlaskProxy());
  process.once("SIGTERM", stopFlask);
  process.once("SIGINT", stopFlask);
  return true;
}
