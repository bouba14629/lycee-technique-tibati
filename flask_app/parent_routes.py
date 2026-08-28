from flask import render_template, request, abort, session
from app import app, db
from models import User, Student, Attendance, ScheduleEntry, Course
from utils import roles_required, general_average, subject_averages, DAYS, TERMS
from eleve_routes import _render_bulletin


def current_parent():
    user = User.query.get(session["user_id"])
    return user.parent_profile


def owned_child(student_id):
    parent = current_parent()
    student = Student.query.get_or_404(student_id)
    if student not in parent.children:
        abort(403)
    return student


@app.route("/parent/enfants")
@roles_required("parent")
def parent_children():
    parent = current_parent()
    data = [(c, general_average(c.id)) for c in parent.children]
    return render_template("parent_children.html", data=data)


@app.route("/parent/enfant/<int:student_id>")
@roles_required("parent")
def parent_child_detail(student_id):
    student = owned_child(student_id)
    term = request.args.get("term", TERMS[0])
    rows = subject_averages(student.id, term=term)
    avg = general_average(student.id, term=term)
    absences = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).limit(10).all()
    return render_template("parent_child_detail.html", student=student, rows=rows, avg=avg,
                            term=term, terms=TERMS, absences=absences)


@app.route("/parent/enfant/<int:student_id>/emploi-du-temps")
@roles_required("parent")
def parent_child_schedule(student_id):
    student = owned_child(student_id)
    entries = ScheduleEntry.query.join(Course).filter(Course.class_id == student.class_id,
                                                        ScheduleEntry.published == True).all()  # noqa: E712
    grid = {d: [] for d in DAYS}
    for e in entries:
        grid[e.day].append(e)
    for d in grid:
        grid[d].sort(key=lambda e: e.start_time)
    return render_template("student_schedule.html", grid=grid, days=DAYS, student=student, parent_view=True)


@app.route("/parent/enfant/<int:student_id>/bulletin")
@roles_required("parent")
def parent_child_bulletin(student_id):
    student = owned_child(student_id)
    return _render_bulletin(student, viewer="parent")
