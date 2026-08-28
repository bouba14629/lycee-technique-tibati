import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-database-resilience.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils"}]:
    del sys.modules[module_name]

from app import app, dashboard_calendar_events
from models import db, SchoolCalendarEvent
from sqlalchemy.exc import OperationalError


with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add(SchoolCalendarEvent(label="Conseil de classe", date_text="20 juin", position=1))
    db.session.commit()
    events = dashboard_calendar_events()
    assert len(events) == 1
    assert events[0].label == "Conseil de classe"

    original_query = SchoolCalendarEvent.query
    retry_calls = {"count": 0}

    class TransientCalendarQuery:
        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            retry_calls["count"] += 1
            if retry_calls["count"] == 1:
                raise OperationalError("SELECT calendar", {}, ConnectionError("connexion transitoirement perdue"))
            return original_query.order_by(SchoolCalendarEvent.position).all()

    try:
        SchoolCalendarEvent.query = TransientCalendarQuery()
        recovered_events = dashboard_calendar_events()
    finally:
        SchoolCalendarEvent.query = original_query

    assert retry_calls["count"] == 2
    assert len(recovered_events) == 1

assert "pool_pre_ping" in open("app.py", encoding="utf-8").read()
assert "pool_recycle" in open("app.py", encoding="utf-8").read()
print("DATABASE_RESILIENCE_TEST_OK")
