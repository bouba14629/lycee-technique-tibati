import express from "express";
import { createServer } from "http";
import { afterEach, describe, expect, it, vi } from "vitest";

const storagePut = vi.hoisted(() => vi.fn());
vi.mock("./storage", () => ({ storagePut }));

import { registerLttMediaUpload } from "./lttFlaskProxy";

describe("student photo media endpoint", () => {
  const servers: ReturnType<typeof createServer>[] = [];

  afterEach(async () => {
    await Promise.all(servers.splice(0).map(server => new Promise<void>(resolve => server.close(() => resolve()))));
    vi.restoreAllMocks();
  });

  async function startServer() {
    const app = express();
    registerLttMediaUpload(app);
    const server = createServer(app);
    await new Promise<void>(resolve => server.listen(0, "127.0.0.1", () => resolve()));
    servers.push(server);
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("Test server did not start");
    return `http://127.0.0.1:${address.port}`;
  }

  it("rejects missing credentials and invalid image types", async () => {
    process.env.JWT_SECRET = "media-test-secret";
    const baseUrl = await startServer();
    const unauthorized = await fetch(`${baseUrl}/api/ltt/media`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: "bytes",
    });
    expect(unauthorized.status).toBe(401);

    const invalid = await fetch(`${baseUrl}/api/ltt/media`, {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-LTT-Internal-Token": "media-test-secret",
        "X-File-Name": "portrait.gif",
        "X-File-Type": "image/gif",
      },
      body: "bytes",
    });
    expect(invalid.status).toBe(400);
    expect(storagePut).not.toHaveBeenCalled();
  });

  it("stores an accepted photo and returns the storage URL", async () => {
    process.env.JWT_SECRET = "media-test-secret";
    storagePut.mockResolvedValue({ key: "students/photo_abc.jpg", url: "/manus-storage/students/photo_abc.jpg" });
    const baseUrl = await startServer();
    const response = await fetch(`${baseUrl}/api/ltt/media`, {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-LTT-Internal-Token": "media-test-secret",
        "X-File-Name": "portrait.JPG",
        "X-File-Type": "image/jpeg",
      },
      body: new Uint8Array([255, 216, 255, 217]),
    });
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ key: "students/photo_abc.jpg", url: "/manus-storage/students/photo_abc.jpg" });
    expect(storagePut).toHaveBeenCalledWith(expect.stringMatching(/^students\/\d+-[a-f0-9]{16}\.jpg$/), expect.any(Buffer), "image/jpeg");
  });
});
