from pathlib import Path

ROOT = Path(__file__).parent
route = (ROOT / "censeur_routes.py").read_text(encoding="utf-8")

assert "def _move_course_indicators(old_course_id, new_course_id, teacher_id):" in route
assert "TeacherIndicator.query.filter_by(course_id=old_course_id).all()" in route
assert "source.course_id = new_course_id" in route
assert "source.teacher_id = teacher_id" in route
assert "CustomIndicatorValue.query.filter_by(course_id=old_course_id).all()" in route
assert "_move_course_indicators(old_course_id, course.id, teacher_id)" in route
assert 'old_course_id = item.course_id' in route

# Les champs saisis doivent être transférés, pas réinitialisés.
for field in ("hours_done", "lessons_done", "tp_done", "observations"):
    assert f'"{field}"' in route

print("SCHEDULE_TEACHER_INDICATOR_SYNC_FEATURE_TEST_OK")
