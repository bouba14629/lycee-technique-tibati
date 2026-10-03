from pathlib import Path

source = (Path(__file__).parent / "enseignant_routes.py").read_text(encoding="utf-8")
start = source.index("def teacher_attendance(course_id):")
end = source.index("def _teacher_schedule_data():", start)
block = source[start:end]

assert "# La fiche d'appel est classée par prénom, A à Z." in block
first_name_key = block.index('(s.first_name or "").strip().casefold()')
last_name_key = block.index('(s.last_name or "").strip().casefold()')
assert first_name_key < last_name_key

print("TEACHER_ATTENDANCE_FIRST_NAME_SORT_FEATURE_TEST_OK")
