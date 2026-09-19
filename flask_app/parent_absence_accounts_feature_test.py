from pathlib import Path

ROOT = Path(__file__).parent
routes = (ROOT / "directeur_routes.py").read_text(encoding="utf-8")
censeur = (ROOT / "censeur_routes.py").read_text(encoding="utf-8")
utils = (ROOT / "utils.py").read_text(encoding="utf-8")
macros = (ROOT / "templates" / "_macros.html").read_text(encoding="utf-8")
users = (ROOT / "templates" / "dir_users.html").read_text(encoding="utf-8")
parent = (ROOT / "templates" / "parent_new.html").read_text(encoding="utf-8")
student = (ROOT / "templates" / "student_enroll.html").read_text(encoding="utf-8")
daily = (ROOT / "templates" / "surveillant_daily_absences.html").read_text(encoding="utf-8")
cumulative = (ROOT / "templates" / "censeur_absences.html").read_text(encoding="utf-8")

assert routes.count('temp_pw = "0000"') >= 2
assert routes.count('student_temp_pw = "0000"') >= 2
assert 'student_ids = request.form.getlist("student_ids", type=int)' in routes
assert 'for sid in student_ids:' in routes
assert 'elif u.role == "parent" and u.parent_profile:' in routes
assert 'elif u.role == "eleve" and u.student_profile:' in routes
assert 'absence_rows.sort(key=lambda row: (-row["hours"]' in censeur
assert 'rows.sort(key=lambda row: (-row["hours"]' in censeur
assert 'name="student_ids"' in parent
assert 'Mot de passe par défaut' in parent
assert 'Mot de passe par défaut : 0000' in student
assert 'data-bs-target="#userEdit{{ u.id }}Modal"' in users
assert 'total_hours = round(sum(row["hours"] for row in rows), 2)' in censeur
assert 'total_hours = round(sum(row["hours"] for row in absence_rows), 2)' in censeur
assert daily.count('Total général des heures d’absence') == 1
assert cumulative.count('Total général des heures d’absence') == 1
assert 'attendance_rate = 100 - absence_rate' in utils
assert '"attendance_rate": attendance_rate' in utils
assert "Taux d'assiduité" in macros
assert 'gaugeAttendance' in macros
print("PARENT_ABSENCE_ACCOUNTS_FEATURE_TEST_OK")
