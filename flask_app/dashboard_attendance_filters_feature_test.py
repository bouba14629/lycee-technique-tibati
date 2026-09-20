from pathlib import Path

ROOT = Path(__file__).parent
app = (ROOT / "app.py").read_text(encoding="utf-8")
utils = (ROOT / "utils.py").read_text(encoding="utf-8")
macros = (ROOT / "templates" / "_macros.html").read_text(encoding="utf-8")

assert "def _dashboard_filter_context(user):" in app
assert 'request.args.getlist("attendance_class_id", type=int)' in app
assert 'request.args.getlist("attendance_subject_id", type=int)' in app
assert 'Subject.query.join(Course).filter(Course.class_id.in_(subject_class_ids))' in app
assert 'attendance_section_id' in macros
assert 'attendance_department_id' in macros
assert 'name="attendance_class_id"' in macros
assert 'name="attendance_subject_id"' in macros
assert 'onchange="scheduleAttendanceFilterSubmit(this.form)"' in macros
assert 'window.setTimeout(function () { form.submit(); }, 500)' in macros
assert 'class_ids=dashboard_filters["class_ids"]' not in app
assert 'dashboard_rates(dashboard_filters["class_ids"], dashboard_filters["subject_ids"])' in app
assert 'def dashboard_rates(class_ids=None, subject_ids=None, teacher_id=None):' in utils
assert 'Course.subject_id.in_(subject_ids)' in utils
assert 'att_q.filter(Attendance.type == "Absence")' in utils
assert 'att_q.filter(Attendance.type == "Retard")' in utils
print("DASHBOARD_ATTENDANCE_FILTERS_FEATURE_TEST_OK")
