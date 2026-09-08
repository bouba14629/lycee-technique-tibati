"""Validation locale obligatoire avant checkpoint.

Chaque test Flask est lancé depuis flask_app avec une base SQLite temporaire
propre. Aucune variable DATABASE_URL de production n’est transmise aux tests.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLASK_DIR = ROOT / "flask_app"

base_env = os.environ.copy()
base_env["LTT_ENV"] = "development"
base_env.pop("LTT_ALLOW_DESTRUCTIVE_TEST_DB", None)

for test_path in sorted(FLASK_DIR.glob("*_test.py")):
    env = base_env.copy()
    sqlite_path = Path("/tmp") / f"ltt-prepublish-{test_path.stem}.sqlite"
    sqlite_path.unlink(missing_ok=True)
    env["DATABASE_URL"] = f"sqlite:///{sqlite_path}"
    print(f"LOCAL_TEST {test_path.name}", flush=True)
    subprocess.run([sys.executable, test_path.name], cwd=FLASK_DIR, env=env, check=True)

print("LOCAL_PREPUBLICATION_OK")
