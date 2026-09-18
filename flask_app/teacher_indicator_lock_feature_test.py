from pathlib import Path

ROOT = Path(__file__).parent
route = (ROOT / "enseignant_routes.py").read_text(encoding="utf-8")
template = (ROOT / "templates" / "teacher_indicators.html").read_text(encoding="utf-8")

planned_fields = [
    "hours_due",
    "lessons_planned",
    "digital_lessons_planned",
    "tp_planned",
    "digital_tp_planned",
]
for field in planned_fields:
    assert f'name="{field}"' in template
    assert f"{{{{ 'readonly' if indicator else '' }}}}" in template
    assert f'"{field}"' in route

assert "if not ind.id:" in route
assert "editable_fields" in route
assert '"hours_done", "lessons_done", "digital_lessons_done"' in route
assert "objectifs prévus sont verrouillés" in template

print("TEACHER_INDICATOR_LOCK_FEATURE_TEST_OK")
