from datetime import date, datetime
from flask import render_template, request, redirect, url_for, flash, session, abort
from app import app, db
from models import Course, Grade, Attendance, Student, Availability, ActivityLog, PlannedAssessment, User
from utils import roles_required, notify, TERMS, TERM_SEQUENCES, OFFICIAL_PERIODS, build_official_grid, DAYS, schedule_extra_hours

DAY_EN = {"Lundi": "MONDAY", "Mardi": "TUESDAY", "Mercredi": "WEDNESDAY", "Jeudi": "THURSDAY",
          "Vendredi": "FRIDAY", "Samedi": "SATURDAY"}
ALLOWED_HOURS_DUE = (22, 25, 44, 50, 66, 75, 88, 100, 110, 125, 132, 154, 176)


def current_teacher():
    user = User.query.get(session["user_id"])
    return user.teacher_profile


@app.route("/enseignant/mes-classes")
@roles_required("enseignant")
def teacher_courses():
    from models import ScheduleEntry
    teacher = current_teacher()
    if not teacher:
        abort(403)
    scheduled_courses = (Course.query.join(ScheduleEntry)
                         .filter(Course.teacher_id == teacher.id)
                         .order_by(Course.class_id, Course.subject_id)
                         .all())
    courses = list({course.id: course for course in scheduled_courses}.values())
    return render_template("teacher_courses.html", teacher=teacher, courses=courses, schedule_synced=True)


@app.route("/enseignant/notes/<int:course_id>/continue/<int:student_id>")
@roles_required("enseignant")
def teacher_devoir_list(course_id, student_id):
    """Détail des notes de contrôle continu d'un élève pour permettre de corriger une erreur de saisie
    (suppression d'une note précise) — la Note Trimestrielle étant désormais une moyenne automatique,
    on ne peut plus simplement 'écraser' une valeur, il faut pouvoir retirer l'entrée fautive."""
    teacher = current_teacher()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != teacher.id:
        abort(403)
    term = request.args.get("term", TERMS[0])
    student = Student.query.get_or_404(student_id)
    grades = (Grade.query.filter_by(student_id=student.id, course_id=course.id, term=term, type="Devoir")
              .order_by(Grade.date.desc()).all())
    return render_template("teacher_devoir_list.html", course=course, student=student, grades=grades, term=term)


@app.route("/enseignant/notes/<int:course_id>/continue/<int:grade_id>/supprimer")
@roles_required("enseignant")
def teacher_devoir_delete(course_id, grade_id):
    teacher = current_teacher()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != teacher.id:
        abort(403)
    g = Grade.query.get_or_404(grade_id)
    if g.course_id != course.id or g.type != "Devoir":
        abort(403)
    student_id = g.student_id
    term = g.term
    db.session.delete(g)
    db.session.commit()
    flash("Note de contrôle continu supprimée.", "info")
    return redirect(url_for("teacher_devoir_list", course_id=course_id, student_id=student_id, term=term))


@app.route("/enseignant/notes/<int:course_id>", methods=["GET", "POST"])
@roles_required("enseignant")
def teacher_grades(course_id):
    teacher = current_teacher()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != teacher.id:
        abort(403)
    term = request.args.get("term", TERMS[0])
    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))

    if request.method == "POST":
        # Une note déjà enregistrée reste modifiable par son enseignant pendant 7 jours.
        # Les notes plus anciennes sont conservées et ne peuvent plus être écrasées.
        if request.form.get("assessment_id", type=int):
            assessment_ref = PlannedAssessment.query.filter_by(id=request.form.get("assessment_id", type=int), course_id=course.id).first()
            if assessment_ref and assessment_ref.submitted_at and (datetime.utcnow() - assessment_ref.submitted_at).days >= 7:
                flash("Cette évaluation est verrouillée après le délai de 7 jours.", "danger")
                return redirect(url_for("teacher_grades", course_id=course_id, term=request.form.get("term", TERMS[0])))
        term = request.form.get("term", TERMS[0])
        seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
        eval_type = request.form.get("type", "Devoir")  # "Devoir", "Évaluation-A" ou "Évaluation-B"
        eval_date = request.form.get("date") or date.today().isoformat()
        assessment_id = request.form.get("assessment_id", type=int)
        planned_assessment = None
        max_value = 20
        if assessment_id:
            planned_assessment = PlannedAssessment.query.filter_by(id=assessment_id, course_id=course.id).first_or_404()
            term = planned_assessment.term
            seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
            eval_date = planned_assessment.scheduled_date.isoformat()
            max_value = planned_assessment.max_value
            if planned_assessment.sequence == seq_a:
                eval_type = "Évaluation-A"
            elif planned_assessment.sequence == seq_b:
                eval_type = "Évaluation-B"
            else:
                abort(403)
        count = 0
        rejected_evaluation_notes = 0
        for student in course.school_class.students:
            key = f"grade_{student.id}"
            val = request.form.get(key, "").strip()
            if not val:
                continue
            try:
                fval = float(val)
            except ValueError:
                continue
            if eval_type != "Devoir" and not 0 <= fval <= 20:
                rejected_evaluation_notes += 1
                continue
            if eval_type == "Devoir":
                # Note continue : chaque saisie s'AJOUTE aux précédentes (jamais remplacée) — la "Note
                # Trimestrielle" affichée sur le bulletin est calculée automatiquement comme leur moyenne.
                db.session.add(Grade(value=fval, max_value=max_value, type="Devoir", term=term,
                                      date=date.fromisoformat(eval_date), student_id=student.id,
                                      course_id=course.id))
            else:
                seq_num = seq_a if eval_type == "Évaluation-A" else seq_b
                existing_grade = Grade.query.filter_by(student_id=student.id, course_id=course.id,
                                                         term=term, type="Évaluation", sequence=seq_num).first()
                if existing_grade:
                    existing_grade.value = fval
                    existing_grade.date = date.fromisoformat(eval_date)
                else:
                    db.session.add(Grade(value=fval, max_value=max_value, type="Évaluation", sequence=seq_num, term=term,
                                          date=date.fromisoformat(eval_date), student_id=student.id,
                                          course_id=course.id))
            count += 1
        if planned_assessment:
            submitted = Grade.query.filter_by(course_id=course.id, term=term, type="Évaluation",
                                               sequence=planned_assessment.sequence).count()
            planned_assessment.status = "Saisie complète" if submitted >= len(course.school_class.students) else "Saisie en cours"
            if planned_assessment.status == "Saisie complète":
                planned_assessment.submitted_at = datetime.utcnow()
        db.session.add(ActivityLog(user_id=session["user_id"],
                                    description=f"Saisie de {count} notes — {course.subject.name} / {course.school_class.name}",
                                    category="pédagogique"))
        db.session.commit()
        if rejected_evaluation_notes:
            flash(f"{rejected_evaluation_notes} note(s) d’évaluation ignorée(s) : une note doit être comprise entre 0 et 20.", "danger")
        flash(f"{count} notes enregistrées.", "success")
        return redirect(url_for("teacher_grades", course_id=course_id, term=term))

    students = sorted(course.school_class.students, key=lambda s: (s.last_name, s.first_name))
    devoirs = {}
    seq_a_grades, seq_b_grades = {}, {}
    for g in Grade.query.filter_by(course_id=course.id, term=term).all():
        if g.type == "Devoir":
            devoirs.setdefault(g.student_id, []).append(g.value)
        elif g.type == "Évaluation" and g.sequence == seq_a:
            seq_a_grades[g.student_id] = g
        elif g.type == "Évaluation" and g.sequence == seq_b:
            seq_b_grades[g.student_id] = g
    from utils import course_average, appreciation_code, _notes_trim_display
    notes_trim_preview = {}
    auto_appreciations = {}
    class_avgs = []
    for student in students:
        avg, nt, ea, eb = course_average(student.id, course.id, term)
        notes_trim_preview[student.id] = _notes_trim_display(nt, ea, eb)
        if avg is not None:
            auto_appreciations[student.id] = appreciation_code(avg)
            class_avgs.append(avg)
    course_class_avg = round(sum(class_avgs) / len(class_avgs), 2) if class_avgs else None
    planned_assessments = PlannedAssessment.query.filter_by(course_id=course.id, term=term).order_by(PlannedAssessment.sequence).all()
    return render_template("teacher_grades.html", course=course, students=students, term=term,
                            terms=TERMS, seq_a=seq_a, seq_b=seq_b, notes_trim_preview=notes_trim_preview,
                            seq_a_grades=seq_a_grades, seq_b_grades=seq_b_grades,
                            auto_appreciations=auto_appreciations, course_class_avg=course_class_avg,
                            nb_evaluated=len(class_avgs), planned_assessments=planned_assessments)


@app.route("/enseignant/appel/<int:course_id>", methods=["GET", "POST"])
@roles_required("enseignant")
def teacher_attendance(course_id):
    from models import ScheduleEntry
    teacher = current_teacher()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != teacher.id:
        abort(403)
    schedule_entry = (ScheduleEntry.query.filter_by(course_id=course.id)
                      .order_by(ScheduleEntry.day, ScheduleEntry.start_time).first())
    scheduled_start = schedule_entry.start_time if schedule_entry else "07:30"
    scheduled_end = schedule_entry.end_time if schedule_entry else "09:30"
    scheduled_day = schedule_entry.day if schedule_entry else ""

    if request.method == "POST":
        session_date = request.form.get("date") or date.today().isoformat()
        start = scheduled_start
        end = scheduled_end
        call_description = f"Appel effectué — {course.subject.name} / {course.school_class.name}"
        already_called = ActivityLog.query.filter_by(
            user_id=session["user_id"], date=date.fromisoformat(session_date),
            description=call_description, category="pédagogique"
        ).first()
        if already_called:
            flash("Cet appel a déjà été enregistré pour cette classe, cette heure et cette matière.", "warning")
            return redirect(url_for("teacher_attendance", course_id=course_id))
        count = 0
        for student in course.school_class.students:
            status = request.form.get(f"status_{student.id}", "Présent")
            if status != "Présent":
                db.session.add(Attendance(date=date.fromisoformat(session_date), start_time=start, end_time=end,
                                           type=status, reason=request.form.get(f"reason_{student.id}", ""),
                                           justified=False, student_id=student.id, course_id=course.id))
                for p in student.parents:
                    notify(p.user_id, f"{student.full_name} : {status.lower()} enregistré(e) le {session_date} en {course.subject.name}.")
                count += 1
        db.session.add(ActivityLog(user_id=session["user_id"],
                                    description=call_description,
                                    category="pédagogique"))
        db.session.commit()
        flash(f"Appel enregistré ({count} absence(s)/retard(s)).", "success")
        return redirect(url_for("teacher_attendance", course_id=course_id))

    students = sorted(course.school_class.students, key=lambda s: (s.last_name, s.first_name))
    return render_template("teacher_attendance.html", course=course, students=students,
                           today=date.today().isoformat(), scheduled_day=scheduled_day,
                           scheduled_start=scheduled_start, scheduled_end=scheduled_end,
                           schedule_entry=schedule_entry)


def _teacher_schedule_data():
    from models import ScheduleEntry
    teacher = current_teacher()
    all_entries = ScheduleEntry.query.join(Course).filter(Course.teacher_id == teacher.id).all()
    section_id = request.args.get("schedule_section_id", type=int)
    department_id = request.args.get("schedule_department_id", type=int)
    class_id = request.args.get("schedule_class_id", type=int)
    subject_id = request.args.get("schedule_subject_id", type=int)

    def unique(values):
        return sorted({item.id: item for item in values}.values(), key=lambda item: item.name.upper())

    sections = unique([entry.course.school_class.department.section for entry in all_entries])
    if section_id not in {item.id for item in sections}:
        section_id = None
    departments = unique([entry.course.school_class.department for entry in all_entries
                          if not section_id or entry.course.school_class.department.section_id == section_id])
    if department_id not in {item.id for item in departments}:
        department_id = None
    classes = sorted({entry.course.school_class.id: entry.course.school_class for entry in all_entries
                      if (not section_id or entry.course.school_class.department.section_id == section_id)
                      and (not department_id or entry.course.school_class.department_id == department_id)}.values(),
                     key=lambda item: item.name.upper())
    if class_id not in {item.id for item in classes}:
        class_id = None
    subjects = unique([entry.course.subject for entry in all_entries
                       if (not section_id or entry.course.school_class.department.section_id == section_id)
                       and (not department_id or entry.course.school_class.department_id == department_id)
                       and (not class_id or entry.course.class_id == class_id)])
    if subject_id not in {item.id for item in subjects}:
        subject_id = None
    entries = [entry for entry in all_entries
               if (not section_id or entry.course.school_class.department.section_id == section_id)
               and (not department_id or entry.course.school_class.department_id == department_id)
               and (not class_id or entry.course.class_id == class_id)
               and (not subject_id or entry.course.subject_id == subject_id)]
    return teacher, entries, {"sections": sections, "departments": departments, "classes": classes,
                              "subjects": subjects, "section_id": section_id, "department_id": department_id,
                              "class_id": class_id, "subject_id": subject_id}


@app.route("/enseignant/emploi-du-temps")
@roles_required("enseignant")
def teacher_schedule():
    from utils import DAYS
    teacher, entries, schedule_filters = _teacher_schedule_data()
    grid = {d: [] for d in DAYS}
    for e in entries:
        grid[e.day].append(e)
    for d in grid:
        grid[d].sort(key=lambda e: e.start_time)
    return render_template("teacher_schedule.html", grid=grid, days=DAYS, teacher=teacher,
                           schedule_filters=schedule_filters)


@app.route("/enseignant/disponibilites", methods=["GET", "POST"])
@roles_required("enseignant")
def teacher_availability():
    teacher = current_teacher()
    if request.method == "POST":
        db.session.add(Availability(teacher_id=teacher.id, day=request.form.get("day"),
                                     start_time=request.form.get("start_time"),
                                     end_time=request.form.get("end_time"),
                                     note=request.form.get("note", "")))
        db.session.commit()
        flash("Disponibilité ajoutée.", "success")
        return redirect(url_for("teacher_availability"))
    return render_template("teacher_availability.html", teacher=teacher)


@app.route("/enseignant/appel/<int:course_id>/fiche")
@roles_required("enseignant")
def teacher_attendance_sheet(course_id):
    teacher = current_teacher()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != teacher.id:
        abort(403)
    session_date = request.args.get("date") or date.today().isoformat()
    students = sorted(course.school_class.students, key=lambda s: (s.last_name, s.first_name))
    d = date.fromisoformat(session_date)
    recs = Attendance.query.filter_by(course_id=course.id, date=d).all()
    records = {r.student_id: r for r in recs}
    schedule_entry = (ScheduleEntry.query.filter_by(course_id=course.id)
                      .order_by(ScheduleEntry.day, ScheduleEntry.start_time).first())
    start_time = schedule_entry.start_time if schedule_entry else "07:30"
    end_time = schedule_entry.end_time if schedule_entry else "09:30"
    return render_template("attendance_sheet.html", course=course, students=students,
                            session_date=session_date, start_time=start_time, end_time=end_time,
                            records=records)


@app.route("/enseignant/appel/<int:course_id>/fiche.pdf")
@roles_required("enseignant")
def teacher_attendance_sheet_pdf(course_id):
    from flask import send_file
    from pdf_utils import render_pdf
    teacher = current_teacher()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != teacher.id:
        abort(403)
    session_date = request.args.get("date") or date.today().isoformat()
    students = sorted(course.school_class.students, key=lambda s: (s.last_name, s.first_name))
    d = date.fromisoformat(session_date)
    recs = Attendance.query.filter_by(course_id=course.id, date=d).all()
    records = {r.student_id: r for r in recs}
    schedule_entry = (ScheduleEntry.query.filter_by(course_id=course.id)
                      .order_by(ScheduleEntry.day, ScheduleEntry.start_time).first())
    start_time = schedule_entry.start_time if schedule_entry else "07:30"
    end_time = schedule_entry.end_time if schedule_entry else "09:30"
    pdf = render_pdf("pdf/attendance_sheet_pdf.html", course=course, students=students,
                      session_date=session_date, start_time=start_time, end_time=end_time, records=records)
    if not pdf:
        abort(500)
    filename = f"Fiche_appel_{course.school_class.name}_{session_date}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/enseignant/activites", methods=["GET", "POST"])
@roles_required("enseignant")
def teacher_activities():
    if request.method == "POST":
        db.session.add(ActivityLog(user_id=session["user_id"], description=request.form.get("description"),
                                    category=request.form.get("category", "pédagogique")))
        db.session.commit()
        flash("Activité enregistrée.", "success")
        return redirect(url_for("teacher_activities"))
    logs = ActivityLog.query.filter_by(user_id=session["user_id"]).order_by(ActivityLog.date.desc()).all()
    return render_template("teacher_activities.html", logs=logs)


@app.route("/enseignant/emploi-du-temps/officiel")
@roles_required("enseignant")
def teacher_schedule_official():
    from utils import filled_official_slots
    teacher, entries, _filters = _teacher_schedule_data()
    grid = build_official_grid(entries)
    hours_faites = filled_official_slots(grid)
    extra_hours = schedule_extra_hours(hours_faites, teacher.hours_due)
    classes_tenues = ", ".join(sorted({e.course.school_class.code or e.course.school_class.name for e in entries}))
    return render_template("schedule_official.html", mode="individuel", teacher=teacher, grid=grid,
                            periods=OFFICIAL_PERIODS, days=DAYS[:5], day_en=DAY_EN,
                            hours_faites=hours_faites, extra_hours=extra_hours, classes_tenues=classes_tenues,
                            pdf_url=url_for("teacher_schedule_official_pdf"),
                            xlsx_url=url_for("teacher_schedule_official_xlsx"))


@app.route("/enseignant/emploi-du-temps/officiel.pdf")
@roles_required("enseignant")
def teacher_schedule_official_pdf():
    from flask import send_file
    from pdf_utils import render_pdf
    from utils import filled_official_slots
    teacher, entries, _filters = _teacher_schedule_data()
    grid = build_official_grid(entries)
    hours_faites = filled_official_slots(grid)
    extra_hours = schedule_extra_hours(hours_faites, teacher.hours_due)
    classes_tenues = ", ".join(sorted({e.course.school_class.code or e.course.school_class.name for e in entries}))
    pdf = render_pdf("pdf/schedule_official_pdf.html", mode="individuel", teacher=teacher, grid=grid,
                      periods=OFFICIAL_PERIODS, days=DAYS[:5], day_en=DAY_EN,
                      hours_faites=hours_faites, extra_hours=extra_hours, classes_tenues=classes_tenues)
    if not pdf:
        abort(500)
    filename = f"Emploi_du_temps_{teacher.user.full_name}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/enseignant/emploi-du-temps/officiel.xlsx")
@roles_required("enseignant")
def teacher_schedule_official_xlsx():
    from flask import send_file
    from excel_utils import teacher_schedule_workbook
    teacher, entries, _filters = _teacher_schedule_data()
    grid_raw = {d: [] for d in DAYS[:5]}
    for e in entries:
        if e.day in grid_raw:
            grid_raw[e.day].append(e)
    planned_slots = filled_official_slots(build_official_grid(entries))
    extra_hours = schedule_extra_hours(planned_slots, teacher.hours_due)
    wb_io = teacher_schedule_workbook(teacher, grid_raw, DAYS[:5], OFFICIAL_PERIODS, planned_slots=planned_slots, extra_hours=extra_hours)
    filename = f"Emploi_du_temps_{teacher.user.full_name}.xlsx".replace(" ", "_")
    return send_file(wb_io, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name=filename)


@app.route("/enseignant/indicateurs", methods=["GET", "POST"])
@roles_required("enseignant")
def teacher_indicators():
    from models import TeacherIndicator, Course, CustomIndicatorType, CustomIndicatorValue
    teacher = current_teacher()
    term = request.args.get("term", TERMS[0]) if request.method == "GET" else request.form.get("term", TERMS[0])
    course_id = request.args.get("course_id", type=int) if request.method == "GET" else request.form.get("course_id", type=int)
    courses = sorted(Course.query.filter(Course.teacher_id == teacher.id, Course.schedule_entries.any()).all(),
                     key=lambda c: (c.school_class.code or c.school_class.name, c.subject.name))
    course = None
    if course_id:
        course = Course.query.get(course_id)
        if not course or course.teacher_id != teacher.id:
            abort(403)

    custom_types = []
    if course:
        teacher_section_id = course.school_class.department.section_id
        custom_types_q = CustomIndicatorType.query
        custom_types_q = custom_types_q.filter(db.or_(CustomIndicatorType.section_id == teacher_section_id,
                                                        CustomIndicatorType.section_id.is_(None)))
        custom_types = custom_types_q.order_by(CustomIndicatorType.label).all()

    if request.method == "POST":
        if not course:
            flash("Veuillez choisir une classe et une matière.", "warning")
            return redirect(url_for("teacher_indicators", term=term))
        submitted_hours_due = request.form.get("hours_due", type=int)
        if submitted_hours_due not in ALLOWED_HOURS_DUE:
            flash("Les heures dues doivent être choisies dans la liste autorisée.", "danger")
            return redirect(url_for("teacher_indicators", term=term, course_id=course.id))
        ind = TeacherIndicator.query.filter_by(course_id=course.id, term=term).first()
        if not ind:
            ind = TeacherIndicator(teacher_id=teacher.id, course_id=course.id, term=term)
            db.session.add(ind)
        # Les objectifs pédagogiques sont verrouillés après le premier enregistrement
        # et ne peuvent être modifiés que par un censeur via son formulaire dédié.
        planned_fields = {"hours_due", "lessons_planned", "digital_lessons_planned",
                          "tp_planned", "digital_tp_planned"}
        editable_fields = ["hours_done", "lessons_done", "digital_lessons_done",
                           "tp_done", "digital_tp_done"]
        planned_values = {field: (getattr(ind, field) if ind.id else request.form.get(field, 0, type=int))
                          for field in planned_fields}
        done_values = {field: request.form.get(field, 0, type=int) for field in editable_fields}
        pairs = [("hours_due", "hours_done"), ("lessons_planned", "lessons_done"),
                 ("digital_lessons_planned", "digital_lessons_done"),
                 ("tp_planned", "tp_done"), ("digital_tp_planned", "digital_tp_done")]
        if any(done_values[done] > planned_values[planned] for planned, done in pairs):
            flash("Chaque valeur réalisée doit être inférieure ou égale à la valeur prévue correspondante.", "danger")
            return redirect(url_for("teacher_indicators", term=term, course_id=course.id))
        if ind.id and any(done_values[done] < getattr(ind, done, 0) for _planned, done in pairs):
            flash("Une valeur réalisée déjà enregistrée ne peut pas être diminuée.", "danger")
            return redirect(url_for("teacher_indicators", term=term, course_id=course.id))
        for field, value in planned_values.items():
            setattr(ind, field, value)
        for field, value in done_values.items():
            setattr(ind, field, value)
        for ct in custom_types:
            cv = CustomIndicatorValue.query.filter_by(indicator_type_id=ct.id, course_id=course.id, term=term).first()
            if not cv:
                cv = CustomIndicatorValue(indicator_type_id=ct.id, course_id=course.id, term=term)
                db.session.add(cv)
            cv.planned = request.form.get(f"custom_{ct.id}_planned", 0, type=int)
            cv.done = request.form.get(f"custom_{ct.id}_done", 0, type=int)
        db.session.commit()
        flash("Indicateurs pédagogiques enregistrés.", "success")
        return redirect(url_for("teacher_indicators", term=term, course_id=course.id))

    ind = TeacherIndicator.query.filter_by(course_id=course.id, term=term).first() if course else None
    custom_values = {}
    if course:
        for ct in custom_types:
            custom_values[ct.id] = CustomIndicatorValue.query.filter_by(indicator_type_id=ct.id, course_id=course.id, term=term).first()
    filled_course_ids = {i.course_id for i in TeacherIndicator.query.filter_by(teacher_id=teacher.id, term=term).all()}
    return render_template("teacher_indicators.html", indicator=ind, term=term, terms=TERMS, teacher=teacher,
                            courses=courses, course=course, filled_course_ids=filled_course_ids,
                            custom_types=custom_types, custom_values=custom_values,
                            allowed_hours_due=ALLOWED_HOURS_DUE)
