from pathlib import Path

ROOT = Path(__file__).parent
route = (ROOT / "enseignant_routes.py").read_text(encoding="utf-8")
template = (ROOT / "templates" / "teacher_indicators.html").read_text(encoding="utf-8")
censeur_route = (ROOT / "censeur_routes.py").read_text(encoding="utf-8")

planned_fields = [
    "hours_due",
    "lessons_planned",
    "digital_lessons_planned",
    "tp_planned",
    "digital_tp_planned",
]
for field in planned_fields:
    assert f'name="{field}"' in template
    assert f"{{{{ 'readonly' if indicator else '' }}}}" not in template
    assert f'"{field}"' in route
assert "editable_fields" in route
assert '"hours_done", "lessons_done", "digital_lessons_done"' in route
assert "Les objectifs prévus peuvent être mis à jour à chaque enregistrement." in template
assert "Chaque valeur réalisée doit être inférieure ou égale à la valeur prévue correspondante." in route
assert "pairs = [(\"hours_due\", \"hours_done\")" in route
assert "Chaque valeur réalisée doit être inférieure ou égale à la valeur prévue correspondante." in censeur_route
assert "pairs = [(\"hours_due\", \"hours_done\")" in censeur_route
assert "planned_values = {field: request.form.get(field, 0, type=int)" in route

print("TEACHER_INDICATOR_LOCK_FEATURE_TEST_OK")
