import os
import sys
from pathlib import Path

TEST_DB = Path("/tmp/ltt-rank-label.sqlite")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LTT_ENV"] = "development"
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")
sys.path.insert(0, os.path.dirname(__file__))

from app import app  # noqa: E402
from utils import format_rank_label  # noqa: E402


with app.app_context():
    assert format_rank_label(1, "M") == "1er"
    assert format_rank_label(1, "F") == "1ère"
    assert format_rank_label(1, "Féminin") == "1ère"
    assert format_rank_label(2, "F") == "2e"
    assert format_rank_label(None, "F") is None
    assert format_rank_label("NC", "F") == "NC"

print("RANK_LABEL_FEATURE_TEST_OK")
