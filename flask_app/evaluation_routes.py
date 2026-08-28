from datetime import date

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import app
from models import Course, Grade, PlannedAssessment, SchoolClass, User, db
from utils import TERMS, login_required, roles_required, user_scoped_class_ids


def _scoped_courses(user):
    query = Course.query.join(SchoolClass)
    class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if class_ids is not None:
        query = query.filter(Course.class_id.in_(class_ids or [-1]))
    return query.order_by(SchoolClass.name).all()


def _assessment_progress(assessment):
    total = len(assessment.course.school_class.students)
    submitted = Grade.query.filter_by(course_id=assessment.course_id, term=assessment.term,
                                      type="Évaluation", sequence=assessment.sequence).count()
    return submitted, total


@app.route("/pedagogie/evaluations", methods=["GET", "POST"])
@roles_required("directeur", "censeur")
def evaluation_plan():
    user = User.query.get_or_404(session["user_id"])
    courses = _scoped_courses(user)
    term = request.args.get("term", TERMS[0])
    selected_sequence = request.args.get("sequence", type=int)
    course_ids = {course.id for course in courses}
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        sequence = request.form.get("sequence", type=int)
        title = request.form.get("title", "").strip()
        scheduled_date = request.form.get("scheduled_date", type=lambda value: date.fromisoformat(value) if value else None)
        max_value = request.form.get("max_value", 20, type=float)
        selected_term = request.form.get("term", TERMS[0])
        if course_id not in course_ids or not sequence or not title or not scheduled_date or sequence not in range(1, 7):
            flash("Renseignez un cours, une séquence, un intitulé et une date valides.", "warning")
        elif not max_value or max_value < 1 or max_value > 20:
            flash("Le barème d’une évaluation doit être compris entre 1 et 20.", "warning")
        elif PlannedAssessment.query.filter_by(course_id=course_id, term=selected_term, sequence=sequence).first():
            flash("Une évaluation est déjà planifiée pour ce cours, cette période et cette séquence.", "warning")
        else:
            db.session.add(PlannedAssessment(course_id=course_id, term=selected_term, sequence=sequence,
                                              title=title, scheduled_date=scheduled_date, max_value=max_value,
                                              created_by_id=user.id))
            db.session.commit()
            flash("Évaluation planifiée. L’enseignant peut désormais saisir les notes associées.", "success")
            return redirect(url_for("evaluation_plan", term=selected_term))
    assessments_query = PlannedAssessment.query.filter_by(term=term)
    if selected_sequence in range(1, 7):
        assessments_query = assessments_query.filter_by(sequence=selected_sequence)
    assessments = assessments_query.order_by(PlannedAssessment.scheduled_date).all()
    if user.role == "censeur":
        assessments = [item for item in assessments if item.course_id in course_ids]
    progress = {item.id: _assessment_progress(item) for item in assessments}
    class_summaries = {}
    for assessment in assessments:
        school_class = assessment.course.school_class
        item = class_summaries.setdefault(school_class.id, {
            "name": school_class.name, "planned": 0, "complete": 0, "pending": 0,
            "submitted": 0, "expected": 0, "grade_values": [],
        })
        submitted, total = progress[assessment.id]
        item["planned"] += 1
        item["complete"] += int(assessment.status == "Saisie complète")
        item["pending"] += int(assessment.status != "Saisie complète")
        item["submitted"] += submitted
        item["expected"] += total
        for grade in Grade.query.filter_by(course_id=assessment.course_id, term=assessment.term,
                                           type="Évaluation", sequence=assessment.sequence).all():
            item["grade_values"].append(grade.value / grade.max_value * 20 if grade.max_value else grade.value)
    for item in class_summaries.values():
        item["submission_rate"] = round(item["submitted"] / item["expected"] * 100) if item["expected"] else 0
        item["average"] = round(sum(item["grade_values"]) / len(item["grade_values"]), 1) if item["grade_values"] else None
    return render_template("evaluation_plan.html", courses=courses, assessments=assessments, progress=progress,
                           class_summaries=sorted(class_summaries.values(), key=lambda item: item["name"]),
                           term=term, terms=TERMS, selected_sequence=selected_sequence, today=date.today().isoformat())


@app.route("/enseignant/evaluations")
@roles_required("enseignant")
def teacher_assessments():
    user = User.query.get_or_404(session["user_id"])
    if not user.teacher_profile:
        abort(403)
    term = request.args.get("term", TERMS[0])
    assessments = (PlannedAssessment.query.join(Course).filter(Course.teacher_id == user.teacher_profile.id,
                                                                 PlannedAssessment.term == term)
                   .order_by(PlannedAssessment.scheduled_date).all())
    progress = {item.id: _assessment_progress(item) for item in assessments}
    return render_template("teacher_assessments.html", assessments=assessments, progress=progress, term=term, terms=TERMS)
