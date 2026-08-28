import json
import os

os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app


with app.test_client() as client:
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    data = json.loads(manifest.data)
    assert data["display"] == "standalone"
    assert data["start_url"] == "/login"
    assert len(data["icons"]) == 2

    worker = client.get("/service-worker.js")
    assert worker.status_code == 200
    assert b"Service-Worker-Allowed" not in worker.data
    assert b"caches.open" in worker.data
    assert b"ltt-shell-v4" in worker.data
    assert b"maconnerie" in worker.data

    installer = client.get("/pwa-install.js")
    assert installer.status_code == 200
    assert b"beforeinstallprompt" in installer.data

    login = client.get("/login")
    assert login.status_code == 200
    assert b"manifest.webmanifest" in login.data
    assert b"password-toggle" in login.data
    assert b"<svg" in login.data
    assert b"2CE1TEFD110320092" in login.data
    assert b"login-hero-orbit" in login.data

print("PWA_FEATURE_TEST_OK")
