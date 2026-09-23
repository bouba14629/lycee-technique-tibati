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
    assert f"{{{{ 'readonly' if indicator else '' }}}}" in template
    assert f'"{field}"' in route
assert "editable_fields" in route
assert '"hours_done", "lessons_done", "digital_lessons_done"' in route
assert "Après le premier enregistrement, les objectifs prévus sont verrouillés." in template
assert "Chaque valeur réalisée doit être inférieure ou égale à la valeur prévue correspondante." in route
assert "pairs = [(\"hours_due\", \"hours_done\")" in route
assert "unlock_planned" not in censeur_route[censeur_route.index("def censeur_indicator_edit"):]
assert "Une valeur réalisée déjà enregistrée ne peut pas être diminuée." not in censeur_route[censeur_route.index("def censeur_indicator_edit"):]
assert "planned_values = {field: (getattr(ind, field) if ind.id else request.form.get(field, 0, type=int))" in route
assert "Les valeurs enregistrées sont chargées directement et peuvent être modifiées par le censeur sans restriction." in (ROOT / "templates" / "censeur_indicators.html").read_text(encoding="utf-8")

print("TEACHER_INDICATOR_LOCK_FEATURE_TEST_OK")
