from pathlib import Path

ROOT = Path(__file__).parent
courses = (ROOT / "templates" / "teacher_courses.html").read_text(encoding="utf-8")
attendance = (ROOT / "templates" / "teacher_attendance.html").read_text(encoding="utf-8")
grades = (ROOT / "templates" / "teacher_grades.html").read_text(encoding="utf-8")
indicators = (ROOT / "templates" / "teacher_indicators.html").read_text(encoding="utf-8")

assert "Date de naissance" in attendance
assert "s.dob.strftime('%d/%m/%Y') if s.dob else '—'" in attendance
assert "student.dob.strftime('%d/%m/%Y') if student.dob else '—'" in courses
assert "Né(e) le / à" in grades
assert "name=\"tp_planned\"" in indicators
assert 'current_user.role != "conseiller_orientation" and indicator' in indicators

print("TEACHER_DOB_COUNSELOR_CONSULTATIONS_FEATURE_TEST_OK")
