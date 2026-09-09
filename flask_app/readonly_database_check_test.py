"""Test du contrôle lecture seule, sur SQLite temporaire uniquement."""

import os
import sqlite3
import sys
from pathlib import Path

TEST_DB = Path("/tmp/ltt-readonly-check.sqlite")
TEST_DB.unlink(missing_ok=True)
connection = sqlite3.connect(TEST_DB)
connection.executescript(
    """
    CREATE TABLE user (id INTEGER PRIMARY KEY);
    CREATE TABLE student (id INTEGER PRIMARY KEY);
    CREATE TABLE school_class (id INTEGER PRIMARY KEY);
    INSERT INTO user DEFAULT VALUES;
    INSERT INTO student DEFAULT VALUES;
    """
)
connection.commit()
connection.close()

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readonly_database_check import inspect_database  # noqa: E402

result = inspect_database(f"sqlite:///{TEST_DB}")
assert result["read_only"] is True
assert result["counts"]["user"] == 1
assert result["counts"]["student"] == 1
assert result["counts"]["school_class"] == 0

try:
    inspect_database("mysql://not-used-in-test")
except RuntimeError as exc:
    assert "lecture" in str(exc)
else:
    raise AssertionError("Une URL non locale doit être refusée sans autorisation explicite")

assert sqlite3.connect(TEST_DB).execute("SELECT COUNT(*) FROM user").fetchone()[0] == 1
print("READONLY_DATABASE_CHECK_TEST_OK")
