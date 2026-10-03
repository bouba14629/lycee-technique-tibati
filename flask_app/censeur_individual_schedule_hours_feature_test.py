from pathlib import Path

ROOT = Path(__file__).parent
route = (ROOT / "censeur_routes.py").read_text(encoding="utf-8")
template = (ROOT / "templates" / "censeur_teacher_schedule_list.html").read_text(encoding="utf-8")

assert "teacher_hours_faites" in route
assert "filled_official_slots(build_official_grid(entries))" in route
assert "teacher_extra_hours" in route
assert "schedule_extra_hours(" in route
assert "<th>Heures dues</th>" in template
assert "<th>Heures faites</th>" in template
assert "<th>Heures supplémentaires</th>" in template
assert "teacher.hours_due or 0" in template
assert "teacher_hours_faites.get(teacher.id, 0)" in template
assert "teacher_extra_hours.get(teacher.id, 0)" in template
assert "Créneaux planifiés" not in template

print("CENSEUR_INDIVIDUAL_SCHEDULE_HOURS_FEATURE_TEST_OK")
