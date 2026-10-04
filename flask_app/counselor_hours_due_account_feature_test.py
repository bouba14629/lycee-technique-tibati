from pathlib import Path

ROOT = Path(__file__).parent
routes = (ROOT / "directeur_routes.py").read_text(encoding="utf-8")
new = (ROOT / "templates" / "dir_user_new.html").read_text(encoding="utf-8")
users = (ROOT / "templates" / "dir_users.html").read_text(encoding="utf-8")

assert 'role in ("enseignant", "conseiller_orientation")' in routes
assert 'hours_due = request.form.get("hours_due"' in routes
assert 'u.role in ("enseignant", "conseiller_orientation")' in routes
assert "counselorHoursFields" in new
assert 'this.value==\'conseiller_orientation\'' in new
assert 'name="hours_due"' in new
assert "u.role in ['enseignant','conseiller_orientation']" in users
assert 'name="hours_due"' in users

print("COUNSELOR_HOURS_DUE_ACCOUNT_FEATURE_TEST_OK")
