from datetime import date
from flask import render_template, request, redirect, url_for, flash, session, abort
from app import app, db
from models import (
    SchoolClass, Course, Room, ScheduleEntry, Attendance, Sanction, Student, Department, Subject, Teacher, User,
    Grade, PlannedAssessment, BulletinApproval, BulletinWorkAppreciation,
)
from utils import (roles_required, check_schedule_conflict, DAYS, general_average, subject_averages,
                    OFFICIAL_PERIODS, build_official_grid, user_scoped_class_ids, user_scoped_department_ids, TERMS,
                    TERM_SEQUENCES, council_statistics, sort_classes_by_level, annual_bulletin_data,
                    bulletin_data, get_current_school_year, is_timetable_only_subject)


@app.route("/censeur/emplois-du-temps", methods=["GET", "POST"])
@roles_required("censeur", "censeur_crm", "conseiller_orientation", "directeur")
def censeur_schedule():
    import uuid
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    # Le Proviseur et le Censeur construisent ; le Censeur CRM et le Conseiller d’orientation consultent.
    is_readonly = user.role in ("censeur_crm", "conseiller_orientation")
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    classes = classes_q.all()
    class_id = request.args.get("class_id", type=int) or (classes[0].id if classes else None)
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    rooms = Room.query.order_by(Room.name).all()
    current_class = SchoolClass.query.get(class_id) if class_id else None
    subjects = Subject.query.filter_by(class_id=current_class.id).order_by(Subject.name).all() if current_class else []
    all_teachers = Teacher.query.join(User).order_by(User.full_name).all()
    # Classes du même niveau pouvant être réunies en tronc commun (matières générales uniquement)
    tronc_commun_classes = []
    if current_class:
        tc_q = SchoolClass.query.filter(SchoolClass.level == current_class.level, SchoolClass.id != current_class.id)
        if scoped_class_ids is not None:
            tc_q = tc_q.filter(SchoolClass.id.in_(scoped_class_ids))
        tronc_commun_classes = tc_q.join(Department).order_by(Department.name).all()
    conflicts = None

    if request.method == "POST":
        if user.role not in ("censeur", "directeur") or is_readonly:
            abort(403)
        if scoped_class_ids is not None and class_id not in scoped_class_ids:
            abort(403)
        subject_id = request.form.get("subject_id", type=int)
        teacher_id = request.form.get("teacher_id", type=int)
        room_id = request.form.get("room_id", type=int)
        day = request.form.get("day")
        start = request.form.get("start_time")
        end = request.form.get("end_time")
        tronc_commun_ids = request.form.getlist("tronc_commun_class_ids", type=int)
        subject = Subject.query.get(subject_id)
        teacher = Teacher.query.get(teacher_id)
        room = Room.query.get(room_id) if room_id else None

        if not current_class or not subject or not teacher or (room_id and not room):
            flash("Sélectionnez une classe, une matière et un enseignant valides. La salle est facultative.", "danger")
            return redirect(url_for("censeur_schedule", class_id=class_id))
        if subject.class_id != current_class.id:
            flash("La matière sélectionnée ne relève pas de cette classe.", "danger")
            return redirect(url_for("censeur_schedule", class_id=class_id))
        if day not in DAYS or not start or not end or len(start) != 5 or len(end) != 5 or start >= end:
            flash("Indiquez un jour et des horaires valides : l’heure de fin doit être postérieure au début.", "danger")
            return redirect(url_for("censeur_schedule", class_id=class_id))

        target_class_ids = [class_id]
        if tronc_commun_ids:
            if subject.category != "Enseignements Généraux":
                flash("Le tronc commun n'est possible que pour les matières d'enseignement général.", "danger")
                return redirect(url_for("censeur_schedule", class_id=class_id))
            if subject.class_id:
                flash("Une matière rattachée à une classe ne peut pas être utilisée en tronc commun.", "danger")
                return redirect(url_for("censeur_schedule", class_id=class_id))
            for cid in tronc_commun_ids:
                if scoped_class_ids is not None and cid not in scoped_class_ids:
                    abort(403)
                other = SchoolClass.query.get(cid)
                if not other or other.level != current_class.level:
                    flash("Le tronc commun ne peut réunir que des classes du même niveau.", "danger")
                    return redirect(url_for("censeur_schedule", class_id=class_id))
            target_class_ids += tronc_commun_ids

        group_key = str(uuid.uuid4()) if len(target_class_ids) > 1 else None
        all_conflicts = []
        for cid in target_class_ids:
            c = check_schedule_conflict(day, start, end, room_id=room_id, teacher_id=teacher_id,
                                         class_id=cid, group_key=group_key)
            all_conflicts += c
        all_conflicts = list(dict.fromkeys(all_conflicts))
        if all_conflicts:
            flash("Conflit détecté : " + " | ".join(all_conflicts), "danger")
        else:
            for cid in target_class_ids:
                course = Course.query.filter_by(subject_id=subject_id, teacher_id=teacher_id, class_id=cid).first()
                if not course:
                    course = Course(subject_id=subject_id, teacher_id=teacher_id, class_id=cid)
                    db.session.add(course)
                    db.session.flush()
                db.session.add(ScheduleEntry(course_id=course.id, room_id=room.id if room else None, day=day,
                                              start_time=start, end_time=end, published=True, group_key=group_key))
            db.session.commit()
            if group_key:
                flash(f"Créneau en tronc commun ajouté pour {len(target_class_ids)} classes.", "success")
            else:
                flash("Créneau ajouté à l'emploi du temps.", "success")
        return redirect(url_for("censeur_schedule", class_id=class_id))

    schedule = ScheduleEntry.query.join(Course).filter(Course.class_id == class_id).all() if class_id else []
    grid = {d: [] for d in DAYS}
    for e in schedule:
        grid[e.day].append(e)
    for d in grid:
        grid[d].sort(key=lambda e: e.start_time)

    return render_template("censeur_schedule.html", classes=classes, class_id=class_id, is_readonly=is_readonly,
                            rooms=rooms, all_teachers=all_teachers, subjects=subjects, grid=grid, days=DAYS,
                            tronc_commun_classes=tronc_commun_classes)


def _censeur_teacher_schedule_in_scope(teacher, user):
    scoped_dept_ids = user_scoped_department_ids(user)
    return scoped_dept_ids is None or teacher.department_id in scoped_dept_ids


def _teacher_schedule_context(teacher):
    from enseignant_routes import DAY_EN
    from utils import OFFICIAL_PERIODS, build_official_grid, filled_official_slots
    entries = ScheduleEntry.query.join(Course).filter(Course.teacher_id == teacher.id).all()
    grid = build_official_grid(entries)
    return {
        "mode": "individuel",
        "teacher": teacher,
        "grid": grid,
        "periods": OFFICIAL_PERIODS,
        "days": DAYS[:5],
        "day_en": DAY_EN,
        "hours_faites": filled_official_slots(grid),
        "classes_tenues": ", ".join(sorted({course.school_class.code or course.school_class.name for course in teacher.courses})),
        "entries": entries,
    }


@app.route("/censeur/emplois-du-temps/enseignants")
@roles_required("censeur", "censeur_crm")
def censeur_teacher_schedule_list():
    user = User.query.get(session["user_id"])
    teachers_q = Teacher.query.join(User)
    scoped_dept_ids = user_scoped_department_ids(user)
    if scoped_dept_ids is not None:
        teachers_q = teachers_q.filter(Teacher.department_id.in_(scoped_dept_ids))
    teachers = teachers_q.order_by(db.func.lower(User.full_name)).all()
    return render_template("censeur_teacher_schedule_list.html", teachers=teachers)


@app.route("/censeur/emplois-du-temps/enseignants/<int:teacher_id>")
@roles_required("censeur", "censeur_crm")
def censeur_teacher_schedule_official(teacher_id):
    user = User.query.get(session["user_id"])
    teacher = Teacher.query.get_or_404(teacher_id)
    if not _censeur_teacher_schedule_in_scope(teacher, user):
        abort(403)
    context = _teacher_schedule_context(teacher)
    context.update(
        pdf_url=url_for("censeur_teacher_schedule_official_pdf", teacher_id=teacher.id),
        xlsx_url=url_for("censeur_teacher_schedule_official_xlsx", teacher_id=teacher.id),
    )
    return render_template("schedule_official.html", **context)


@app.route("/censeur/emplois-du-temps/enseignants/<int:teacher_id>/officiel.pdf")
@roles_required("censeur", "censeur_crm")
def censeur_teacher_schedule_official_pdf(teacher_id):
    from flask import send_file
    from pdf_utils import render_pdf
    user = User.query.get(session["user_id"])
    teacher = Teacher.query.get_or_404(teacher_id)
    if not _censeur_teacher_schedule_in_scope(teacher, user):
        abort(403)
    context = _teacher_schedule_context(teacher)
    context.pop("entries")
    pdf = render_pdf("pdf/schedule_official_pdf.html", **context)
    if not pdf:
        abort(500)
    filename = f"Emploi_du_temps_{teacher.user.full_name}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/censeur/emplois-du-temps/enseignants/<int:teacher_id>/officiel.xlsx")
@roles_required("censeur", "censeur_crm")
def censeur_teacher_schedule_official_xlsx(teacher_id):
    from flask import send_file
    from excel_utils import teacher_schedule_workbook
    from utils import OFFICIAL_PERIODS
    user = User.query.get(session["user_id"])
    teacher = Teacher.query.get_or_404(teacher_id)
    if not _censeur_teacher_schedule_in_scope(teacher, user):
        abort(403)
    context = _teacher_schedule_context(teacher)
    grid_raw = {day: [] for day in DAYS[:5]}
    for entry in context["entries"]:
        if entry.day in grid_raw:
            grid_raw[entry.day].append(entry)
    workbook = teacher_schedule_workbook(teacher, grid_raw, DAYS[:5], OFFICIAL_PERIODS)
    filename = f"Emploi_du_temps_{teacher.user.full_name}.xlsx".replace(" ", "_")
    return send_file(workbook, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=filename)


@app.route("/censeur/emplois-du-temps/<int:entry_id>/supprimer")
@roles_required("censeur", "censeur_crm")
def censeur_schedule_delete(entry_id):
    user = User.query.get(session["user_id"])
    if user.role == "censeur_crm":
        abort(403)  # Censeur CRM : consultation uniquement désormais
    e = ScheduleEntry.query.get_or_404(entry_id)
    scoped_class_ids = user_scoped_class_ids(user)
    if scoped_class_ids is not None and e.course.class_id not in scoped_class_ids:
        abort(403)
    class_id = e.course.class_id
    db.session.delete(e)
    db.session.commit()
    flash("Créneau supprimé.", "info")
    return redirect(url_for("censeur_schedule", class_id=class_id))


@app.route("/censeur/absences")
@roles_required("surveillant_general", "conseiller_orientation")
def censeur_absences():
    user = User.query.get(session["user_id"])
    class_id = request.args.get("class_id", type=int)
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "surveillant_general" else None
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    classes = classes_q.all()
    if class_id and scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    records_q = Attendance.query.join(Student).filter(Attendance.type == "Absence")
    if class_id:
        records_q = records_q.filter(Student.class_id == class_id)
    elif scoped_class_ids is not None:
        records_q = records_q.filter(Student.class_id.in_(scoped_class_ids))
    records = records_q.order_by(Attendance.date.desc()).all()
    student_hours = {}
    for record in records:
        student_hours.setdefault(record.student_id, _absence_hours(record.student_id))
    return render_template("censeur_absences.html", records=records, classes=classes, class_id=class_id,
                           student_hours=student_hours)


def _absence_class_rows(user, class_id):
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "surveillant_general" else None
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    school_class = SchoolClass.query.get_or_404(class_id)
    rows = []
    for student in sorted(school_class.students, key=lambda item: (item.last_name, item.first_name)):
        records = Attendance.query.filter_by(student_id=student.id, type="Absence").order_by(Attendance.date.desc()).all()
        rows.append({"student": student, "hours": _absence_hours(student.id), "count": len(records), "records": records})
    return school_class, rows


@app.route("/surveillant/absences/classe/<int:class_id>/export.xlsx")
@roles_required("surveillant_general")
def surveillant_absences_export_xlsx(class_id):
    from flask import send_file
    from excel_utils import absence_hours_workbook
    school_class, rows = _absence_class_rows(User.query.get(session["user_id"]), class_id)
    return send_file(absence_hours_workbook(school_class, rows), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"Absences_{school_class.name}.xlsx".replace(" ", "_"))


@app.route("/surveillant/absences/classe/<int:class_id>/export.pdf")
@roles_required("surveillant_general")
def surveillant_absences_export_pdf(class_id):
    from flask import send_file, abort
    from pdf_utils import render_pdf
    school_class, rows = _absence_class_rows(User.query.get(session["user_id"]), class_id)
    pdf = render_pdf("pdf/absence_class_pdf.html", school_class=school_class, rows=rows)
    if not pdf:
        abort(500)
    return send_file(pdf, mimetype="application/pdf", as_attachment=True,
                     download_name=f"Absences_{school_class.name}.pdf".replace(" ", "_"))


@app.route("/censeur/absences/<int:att_id>/justifier")
@roles_required("surveillant_general")
def censeur_absence_justify(att_id):
    user = User.query.get(session["user_id"])
    a = Attendance.query.get_or_404(att_id)
    scoped_class_ids = user_scoped_class_ids(user)
    if scoped_class_ids is not None and a.student.class_id not in scoped_class_ids:
        abort(403)
    a.justified = True
    db.session.commit()
    flash("Absence marquée comme justifiée.", "success")
    return redirect(url_for("censeur_absences"))


@app.route("/censeur/conseils-de-classe")
@roles_required("censeur", "directeur")
def censeur_conseil():
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    classes = classes_q.all()
    class_id = request.args.get("class_id", type=int)
    if class_id and scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    report = []
    cls = None
    if class_id:
        cls = SchoolClass.query.get_or_404(class_id)
        for st in cls.students:
            report.append({
                "student": st,
                "avg": general_average(st.id),
                "subjects": subject_averages(st.id),
                "absences": Attendance.query.filter_by(student_id=st.id, type="Absence").count(),
                "sanctions": Sanction.query.filter_by(student_id=st.id).count(),
            })
        report.sort(key=lambda r: -(r["avg"] or 0))
    return render_template("censeur_conseil.html", classes=classes, class_id=class_id, cls=cls, report=report)


@app.route("/censeur/emplois-du-temps/<int:class_id>/officiel")
@roles_required("censeur", "censeur_crm", "conseiller_orientation", "directeur")
def class_schedule_official(class_id):
    from models import ScheduleEntry, Course
    from enseignant_routes import DAY_EN
    cls = SchoolClass.query.get_or_404(class_id)
    entries = ScheduleEntry.query.join(Course).filter(Course.class_id == class_id).all()
    grid = build_official_grid(entries)
    return render_template("schedule_official.html", mode="classe", school_class=cls, grid=grid,
                            periods=OFFICIAL_PERIODS, days=DAYS[:5], day_en=DAY_EN,
                            pdf_url=url_for("class_schedule_official_pdf", class_id=class_id),
                            xlsx_url=url_for("class_schedule_official_xlsx", class_id=class_id))


@app.route("/censeur/emplois-du-temps/<int:class_id>/officiel.pdf")
@roles_required("censeur", "censeur_crm", "conseiller_orientation", "directeur")
def class_schedule_official_pdf(class_id):
    from flask import send_file, abort
    from models import ScheduleEntry, Course
    from pdf_utils import render_pdf
    from enseignant_routes import DAY_EN
    cls = SchoolClass.query.get_or_404(class_id)
    entries = ScheduleEntry.query.join(Course).filter(Course.class_id == class_id).all()
    grid = build_official_grid(entries)
    pdf = render_pdf("pdf/schedule_official_pdf.html", mode="classe", school_class=cls, grid=grid,
                      periods=OFFICIAL_PERIODS, days=DAYS[:5], day_en=DAY_EN)
    if not pdf:
        abort(500)
    filename = f"Emploi_du_temps_{cls.name}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/censeur/emplois-du-temps/<int:class_id>/officiel.xlsx")
@roles_required("censeur", "censeur_crm", "conseiller_orientation", "directeur")
def class_schedule_official_xlsx(class_id):
    from flask import send_file
    from models import ScheduleEntry, Course
    from excel_utils import class_schedule_workbook
    cls = SchoolClass.query.get_or_404(class_id)
    entries = ScheduleEntry.query.join(Course).filter(Course.class_id == class_id).all()
    grid_raw = {d: [] for d in DAYS[:5]}
    for e in entries:
        if e.day in grid_raw:
            grid_raw[e.day].append(e)
    wb_io = class_schedule_workbook(cls, grid_raw, DAYS[:5], OFFICIAL_PERIODS)
    filename = f"Emploi_du_temps_{cls.name}.xlsx".replace(" ", "_")
    return send_file(wb_io, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name=filename)


@app.route("/censeur/bulletins")
@roles_required("censeur", "directeur")
def censeur_bulletins():
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    all_classes = classes_q.all()
    class_id = request.args.get("class_id", type=int)
    department_id = request.args.get("department_id", type=int)
    accessible_class_ids = {school_class.id for school_class in all_classes}
    accessible_department_ids = {school_class.department_id for school_class in all_classes}
    if class_id and class_id not in accessible_class_ids:
        abort(403)
    selected_class = next((school_class for school_class in all_classes if school_class.id == class_id), None)
    if selected_class and department_id is None:
        department_id = selected_class.department_id
    if department_id is not None and department_id not in accessible_department_ids:
        abort(403)
    if selected_class and selected_class.department_id != department_id:
        abort(400)
    departments = (Department.query.filter(Department.id.in_(sorted(accessible_department_ids)))
                   .order_by(Department.name).all()) if accessible_department_ids else []
    classes = [school_class for school_class in all_classes if school_class.department_id == department_id]
    classes_by_department = {}
    for school_class in all_classes:
        classes_by_department.setdefault(str(school_class.department_id), []).append({
            "id": school_class.id,
            "name": school_class.name,
            "department": school_class.department.name,
        })
    period_options = TERMS[:2] + ["Annuel"]
    term = request.args.get("term", TERMS[0])
    if term == "Trimestre 3":
        term = "Annuel"
    if term not in period_options:
        term = TERMS[0]
    search = request.args.get("q", "").strip()
    students = []
    current_class = None
    class_teachers = []
    if class_id:
        current_class = SchoolClass.query.get_or_404(class_id)
        students = sorted(current_class.students, key=lambda s: s.last_name)
        class_teachers = sorted(current_class.department.teachers, key=lambda teacher: teacher.user.full_name)
        if search:
            like = search.lower()
            students = [s for s in students if like in s.full_name.lower() or like in s.matricule.lower()]
    approval = BulletinApproval.query.filter_by(class_id=class_id, term=term, status="Validé").first() if class_id else None
    annual_approval = BulletinApproval.query.filter_by(class_id=class_id, term="Annuel", status="Validé").first() if class_id else None
    return render_template("censeur_bulletins.html", classes=classes, all_classes=all_classes,
                           departments=departments, department_id=department_id,
                           classes_by_department=classes_by_department,
                           class_id=class_id, students=students, search=search,
                           term=term, terms=period_options, approval=approval, annual_approval=annual_approval,
                           current_class=current_class, class_teachers=class_teachers)


def _bulletins_url(class_id=None, term=None):
    params = {}
    if class_id:
        school_class = db.session.get(SchoolClass, class_id)
        params.update(class_id=class_id, department_id=school_class.department_id if school_class else None)
    if term:
        params["term"] = term
    return url_for("censeur_bulletins", **params)


@app.route("/censeur/classes/<int:class_id>/professeur-principal", methods=["POST"])
@roles_required("censeur")
def censeur_class_homeroom(class_id):
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user)
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    school_class = SchoolClass.query.get_or_404(class_id)
    teacher_id = request.form.get("teacher_id", type=int)
    teacher = Teacher.query.get(teacher_id) if teacher_id else None
    if teacher and teacher.department_id != school_class.department_id:
        flash("Le professeur principal doit appartenir au département de cette classe.", "danger")
        return redirect(_bulletins_url(class_id, request.form.get("term", TERMS[0])))
    school_class.homeroom_teacher_id = teacher.id if teacher else None
    db.session.commit()
    flash(f"Professeur principal de {school_class.name} mis à jour.", "success")
    return redirect(_bulletins_url(class_id, request.form.get("term", TERMS[0])))


DEFAULT_HONOR_CONGRATULATIONS = "pour son travail apprécié et sa bonne conduite."


def _honor_congratulations():
    text = " ".join(request.args.get("congratulations", "").split())
    return (text[:280] or DEFAULT_HONOR_CONGRATULATIONS)


def _honor_recipients(school_class, term):
    recipients = []
    for student in school_class.students:
        data = bulletin_data(student, term=term)
        if not data or data.get("overall_avg") is None:
            continue
        if not 12 <= data["overall_avg"] <= 20:
            continue
        rank = data.get("rank")
        if rank == 1:
            suffix = "ère" if student.sex in {"F", "Féminin"} else "er"
            rank_label = f"1{suffix}"
        else:
            rank_label = f"{rank}e" if rank else "—"
        recipients.append({"student": student, "average": data["overall_avg"], "rank": rank, "rank_label": rank_label,
                           "class_size": data.get("class_size", 0)})
    recipients.sort(key=lambda item: (-item["average"], item["student"].last_name, item["student"].first_name))
    return recipients


def _honor_classes(user):
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level, SchoolClass.name)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    return classes_q.all(), scoped_class_ids


def _honor_scope(user, term, class_id=None):
    classes, scoped_class_ids = _honor_classes(user)
    if class_id and scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    if class_id:
        classes = [school_class for school_class in classes if school_class.id == class_id]
        if not classes:
            abort(404)
    rows = []
    for school_class in classes:
        for recipient in _honor_recipients(school_class, term):
            rows.append({"school_class": school_class, **recipient})
    rows.sort(key=lambda item: (item["school_class"].name, item["rank"] or 999,
                                item["student"].last_name, item["student"].first_name))
    return rows


@app.route("/censeur/bulletins/classe/<int:class_id>/tableaux-honneur/apercu")
@roles_required("censeur", "directeur")
def censeur_honor_roll_preview(class_id):
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    school_class = SchoolClass.query.get_or_404(class_id)
    term = request.args.get("term", TERMS[0])
    recipients = _honor_recipients(school_class, term)
    if not recipients:
        return "<p style='font-family:Arial;padding:24px'>Aucun élève de cette classe n’a une moyenne complète comprise entre 12/20 et 20/20 pour ce trimestre.</p>", 404
    return render_template("pdf/honor_roll_pdf.html", school_class=school_class, recipients=recipients, term=term,
                           school_year=get_current_school_year(), congratulations=_honor_congratulations())


@app.route("/censeur/tableaux-honneur/eleve/<int:student_id>/apercu")
@roles_required("censeur", "directeur")
def censeur_honor_roll_student_preview(student_id):
    user = User.query.get(session["user_id"])
    student = Student.query.get_or_404(student_id)
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if scoped_class_ids is not None and student.class_id not in scoped_class_ids:
        abort(403)
    term = request.args.get("term", TERMS[0])
    recipient = next((item for item in _honor_recipients(student.school_class, term) if item["student"].id == student.id), None)
    if not recipient:
        return "<p style='font-family:Arial;padding:24px'>Cet élève n’est pas admissible au tableau d’honneur pour ce trimestre.</p>", 404
    return render_template("pdf/honor_roll_pdf.html", school_class=student.school_class, recipients=[recipient], term=term,
                           school_year=get_current_school_year(), congratulations=_honor_congratulations())


@app.route("/censeur/bulletins/classe/<int:class_id>/tableaux-honneur.pdf")
@roles_required("censeur", "directeur")
def censeur_honor_roll_pdf(class_id):
    from flask import send_file
    from pdf_utils import render_pdf
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    school_class = SchoolClass.query.get_or_404(class_id)
    term = request.args.get("term", TERMS[0])
    recipients = _honor_recipients(school_class, term)
    if not recipients:
        flash("Aucun élève de cette classe n’a une moyenne complète comprise entre 12/20 et 20/20 pour ce trimestre.", "warning")
        return redirect(url_for("censeur_bulletins", class_id=class_id, term=term))
    pdf = render_pdf("pdf/honor_roll_pdf.html", school_class=school_class, recipients=recipients, term=term,
                     school_year=get_current_school_year(), congratulations=_honor_congratulations())
    if not pdf:
        abort(500)
    filename = f"Tableaux_honneur_{school_class.name}_{term}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/censeur/tableaux-honneur/registre")
@roles_required("censeur", "directeur")
def censeur_honor_roll_register():
    user = User.query.get(session["user_id"])
    term = request.args.get("term", TERMS[0])
    class_id = request.args.get("class_id", type=int)
    classes, _ = _honor_classes(user)
    rows = _honor_scope(user, term, class_id)
    return render_template("honor_roll_register.html", rows=rows, term=term, terms=TERMS, classes=classes,
                           class_id=class_id, school_year=get_current_school_year())


@app.route("/censeur/tableaux-honneur/registre/export.xlsx")
@roles_required("censeur", "directeur")
def censeur_honor_roll_register_export():
    from flask import send_file
    from excel_utils import honor_roll_register_workbook
    user = User.query.get(session["user_id"])
    term = request.args.get("term", TERMS[0])
    class_id = request.args.get("class_id", type=int)
    workbook = honor_roll_register_workbook(_honor_scope(user, term, class_id), term, get_current_school_year())
    filename = f"Registre_tableaux_honneur_{term}.xlsx".replace(" ", "_")
    return send_file(workbook, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=filename)


@app.route("/censeur/tableaux-honneur/registre/export.pdf")
@roles_required("censeur", "directeur")
def censeur_honor_roll_register_export_pdf():
    from flask import send_file
    from pdf_utils import render_pdf
    user = User.query.get(session["user_id"])
    term = request.args.get("term", TERMS[0])
    class_id = request.args.get("class_id", type=int)
    classes, _ = _honor_classes(user)
    selected_class = next((school_class for school_class in classes if school_class.id == class_id), None) if class_id else None
    rows = _honor_scope(user, term, class_id)
    pdf = render_pdf("pdf/honor_roll_register_pdf.html", rows=rows, term=term, school_year=get_current_school_year(),
                     selected_class=selected_class)
    if not pdf:
        abort(500)
    suffix = selected_class.name if selected_class else "toutes_classes"
    filename = f"Registre_tableaux_honneur_{term}_{suffix}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.route("/censeur/bulletins/annuel/<int:student_id>.pdf")
@roles_required("censeur", "directeur")
def censeur_annual_bulletin_pdf(student_id):
    from flask import send_file
    from pdf_utils import render_pdf, student_photo_pdf_path
    user = User.query.get(session["user_id"])
    student = Student.query.get_or_404(student_id)
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if scoped_class_ids is not None and student.class_id not in scoped_class_ids:
        abort(403)
    data = annual_bulletin_data(student)
    if not data:
        abort(404)
    approval = BulletinApproval.query.filter_by(class_id=student.class_id, term="Annuel", status="Validé").first()
    pdf = render_pdf("pdf/bulletin_annual_pdf.html", student=student, data=data, school_year="2025-2026", approval=approval,
                     student_photo_path=student_photo_pdf_path(student.photo))
    if not pdf:
        abort(500)
    inline_preview = request.args.get("preview") == "1"
    return send_file(pdf, mimetype="application/pdf", as_attachment=not inline_preview,
                     download_name=f"Bulletin_annuel_{student.matricule}.pdf")


@app.route("/censeur/bulletins/annuel/<int:student_id>")
@roles_required("censeur", "directeur")
def censeur_annual_bulletin_preview(student_id):
    user = User.query.get(session["user_id"])
    student = Student.query.get_or_404(student_id)
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if scoped_class_ids is not None and student.class_id not in scoped_class_ids:
        abort(403)
    data = annual_bulletin_data(student)
    if not data:
        return render_template("bulletin_annual_unavailable.html", student=student), 404
    approval = BulletinApproval.query.filter_by(class_id=student.class_id, term="Annuel", status="Validé").first()
    return render_template("bulletin_annual_preview.html", student=student, data=data, school_year="2025-2026", approval=approval,
                           pdf_url=url_for("censeur_annual_bulletin_pdf", student_id=student.id),
                           preview_pdf_url=url_for("censeur_annual_bulletin_pdf", student_id=student.id, preview=1))


@app.route("/censeur/bulletins/classe/<int:class_id>/annuels/generer")
@roles_required("censeur", "directeur")
def censeur_annual_bulletins_generation_preview(class_id):
    """Prépare les données annuelles de toute une classe avant l’impression individuelle par le Censeur."""
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    school_class = SchoolClass.query.get_or_404(class_id)
    rows = []
    for student in sorted(school_class.students, key=lambda item: (item.last_name, item.first_name)):
        annual_data = annual_bulletin_data(student)
        rows.append({"student": student, "data": annual_data})
    approval = BulletinApproval.query.filter_by(class_id=class_id, term="Annuel", status="Validé").first()
    return render_template("annual_class_generation_preview.html", school_class=school_class, rows=rows,
                           approval=approval, school_year="2025-2026")


@app.route("/censeur/bulletins/classe/<int:class_id>/valider-annuel", methods=["POST"])
@roles_required("censeur")
def censeur_bulletins_validate_annual(class_id):
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user)
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    release_date = request.form.get("official_release_date")
    try:
        release_date = datetime.strptime(release_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        flash("Indiquez la date officielle de remise annuelle.", "danger")
        return redirect(_bulletins_url(class_id, "Annuel"))
    approval = BulletinApproval.query.filter_by(class_id=class_id, term="Annuel").first()
    if not approval:
        approval = BulletinApproval(class_id=class_id, term="Annuel")
        db.session.add(approval)
    approval.status = "Validé"
    approval.validated_by_id = user.id
    approval.validated_at = datetime.utcnow()
    approval.official_release_date = release_date
    approval.revocation_reason = None
    db.session.commit()
    flash("Bulletins annuels validés : le visa numérique sera apposé aux PDF.", "success")
    return redirect(_bulletins_url(class_id, "Annuel"))


@app.route("/censeur/bulletins/classe/<int:class_id>/valider", methods=["POST"])
@roles_required("censeur")
def censeur_bulletins_validate(class_id):
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user)
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    cls = SchoolClass.query.get_or_404(class_id)
    term = request.form.get("term", TERMS[0])
    release_value = request.form.get("official_release_date", "").strip()
    try:
        official_release_date = __import__("datetime").date.fromisoformat(release_value)
    except ValueError:
        flash("Choisissez la date officielle de remise avant de valider la diffusion.", "warning")
        return redirect(_bulletins_url(class_id, term))
    from utils import bulletin_data
    pending = []
    for student in cls.students:
        data = bulletin_data(student, term=term)
        if any(row.get("pending") for category in data.get("categories", []) for row in category["rows"]):
            pending.append(student.full_name)
    if pending:
        flash(f"Validation impossible : des notes sont encore en attente pour {len(pending)} élève(s).", "warning")
        return redirect(_bulletins_url(class_id, term))
    approval = BulletinApproval.query.filter_by(class_id=class_id, term=term).first()
    if approval is None:
        approval = BulletinApproval(class_id=class_id, term=term, validated_by_id=user.id,
                                    official_release_date=official_release_date)
        db.session.add(approval)
    else:
        approval.status = "Validé"
        approval.validated_by_id = user.id
        approval.validated_at = __import__("datetime").datetime.utcnow()
        approval.official_release_date = official_release_date
        approval.revoked_by_id = None
        approval.revoked_at = None
        approval.revocation_reason = None
    db.session.commit()
    flash(f"Les bulletins de {cls.name} pour {term} sont validés. La notification sera visible le {official_release_date.strftime('%d/%m/%Y')}, jour de remise officielle.", "success")
    return redirect(_bulletins_url(class_id, term))


@app.route("/censeur/bulletins/<int:student_id>/appreciation", methods=["GET", "POST"])
@roles_required("censeur")
def censeur_bulletin_work_appreciation(student_id):
    user = User.query.get(session["user_id"])
    student = Student.query.get_or_404(student_id)
    scoped_class_ids = user_scoped_class_ids(user)
    if scoped_class_ids is not None and student.class_id not in scoped_class_ids:
        abort(403)
    term = request.values.get("term", TERMS[0])
    if term not in TERMS:
        abort(400)
    appreciation = BulletinWorkAppreciation.query.filter_by(student_id=student.id, term=term).first()
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if not content:
            flash("Saisissez une appréciation avant d’enregistrer.", "warning")
        elif len(content) > 500:
            flash("L’appréciation ne doit pas dépasser 500 caractères.", "warning")
        else:
            if not appreciation:
                appreciation = BulletinWorkAppreciation(student_id=student.id, term=term, updated_by_id=user.id, content=content)
                db.session.add(appreciation)
            else:
                appreciation.content = content
                appreciation.updated_by_id = user.id
            db.session.commit()
            flash("Appréciation du travail enregistrée sur le bulletin.", "success")
            return redirect(_bulletins_url(student.class_id, term))
    return render_template("censeur_bulletin_appreciation.html", student=student, term=term, appreciation=appreciation)


@app.route("/censeur/bulletins/classe/<int:class_id>/annuler-validation", methods=["POST"])
@roles_required("censeur")
def censeur_bulletins_revoke_validation(class_id):
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user)
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    term = request.form.get("term", TERMS[0])
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("Indiquez le motif du retrait de validation.", "warning")
        return redirect(_bulletins_url(class_id, term))
    approval = BulletinApproval.query.filter_by(class_id=class_id, term=term, status="Validé").first()
    if approval is None:
        flash("Aucune validation active à annuler.", "warning")
        return redirect(_bulletins_url(class_id, term))
    approval.status = "Retiré"
    approval.revoked_by_id = user.id
    approval.revoked_at = __import__("datetime").datetime.utcnow()
    approval.revocation_reason = reason
    db.session.commit()
    flash("Validation retirée : les bulletins redeviennent indisponibles à la diffusion.", "info")
    return redirect(_bulletins_url(class_id, term))


@app.route("/censeur/bulletins/classe/<int:class_id>/telecharger.pdf")
@roles_required("censeur", "directeur")
def censeur_bulletins_class_pdf(class_id):
    from flask import send_file
    from pdf_utils import render_pdf, student_photo_pdf_path
    from utils import annual_bulletin_data, bulletin_data, TERMS as T, TERM_SEQUENCES, TERM_ORDINALS
    user = User.query.get(session["user_id"])
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    if scoped_class_ids is not None and class_id not in scoped_class_ids:
        abort(403)
    cls = SchoolClass.query.get_or_404(class_id)
    term = request.args.get("term", T[0])
    if term == "Trimestre 3":
        term = "Annuel"
    approval = BulletinApproval.query.filter_by(class_id=class_id, term=term, status="Validé").first()
    students = sorted(cls.students, key=lambda s: (s.last_name, s.first_name))
    if term == "Annuel":
        students_data = [{"student": st, "data": annual_bulletin_data(st), "photo_path": student_photo_pdf_path(st.photo)} for st in students]
        pdf = render_pdf("pdf/class_annual_bulletins_pdf.html", students_data=students_data,
                         school_year=get_current_school_year(), approval=approval)
        if not pdf:
            abort(500)
        filename = f"Bulletins_annuels_{cls.name}.pdf".replace(" ", "_")
        return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)
    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
    students_data = []
    for st in students:
        students_data.append({
            "student": st,
            "data": bulletin_data(st, term=term),
            "bulletin_ref": f"{st.matricule}-T{T.index(term)+1}-2025",
            "photo_path": student_photo_pdf_path(st.photo),
        })
    pdf = render_pdf("pdf/class_bulletins_pdf.html", students_data=students_data, term=term,
                      TERM_SEQ_A=seq_a, TERM_SEQ_B=seq_b, term_ordinal=TERM_ORDINALS.get(term, ""), approval=approval)
    if not pdf:
        abort(500)
    filename = f"Bulletins_{cls.name}_{term}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


def _sanctioned_students_query(user, search, date_from, date_to):
    from models import Sanction
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "surveillant_general" else None
    q = Sanction.query.join(Student)
    if scoped_class_ids is not None:
        q = q.filter(Student.class_id.in_(scoped_class_ids))
    if date_from:
        q = q.filter(Sanction.date >= date_from)
    if date_to:
        q = q.filter(Sanction.date <= date_to)
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(Student.first_name.ilike(like), Student.last_name.ilike(like), Student.matricule.ilike(like)))
    return q.order_by(Sanction.date.desc()).all()


def _absence_hours(student_id):
    total = 0.0
    for a in Attendance.query.filter_by(student_id=student_id, type="Absence").all():
        try:
            h1, m1 = map(int, a.start_time.split(":"))
            h2, m2 = map(int, a.end_time.split(":"))
            total += max(0, (h2 * 60 + m2 - h1 * 60 - m1) / 60)
        except Exception:
            pass
    return round(total, 1)


@app.route("/surveillant/sanctions")
@roles_required("surveillant_general")
def surveillant_sanctions():
    from utils import parse_date
    user = User.query.get(session["user_id"])
    search = request.args.get("q", "").strip()
    date_from = parse_date(request.args.get("date_from", ""))
    date_to = parse_date(request.args.get("date_to", ""))
    sanctions = _sanctioned_students_query(user, search, date_from, date_to)
    rows = []
    seen = set()
    for s in sanctions:
        if s.student_id in seen:
            continue
        seen.add(s.student_id)
        rows.append({
            "student": s.student,
            "nb_sanctions": Sanction.query.filter_by(student_id=s.student_id).count(),
            "absence_hours": _absence_hours(s.student_id),
            "last_sanction": s,
        })
    return render_template("surveillant_sanctions.html", rows=rows, search=search,
                            date_from=request.args.get("date_from", ""), date_to=request.args.get("date_to", ""))


@app.route("/surveillant/sanctions/export.xlsx")
@roles_required("surveillant_general")
def surveillant_sanctions_export():
    from flask import send_file
    from utils import parse_date
    from excel_utils import sanctions_workbook
    user = User.query.get(session["user_id"])
    search = request.args.get("q", "").strip()
    date_from = parse_date(request.args.get("date_from", ""))
    date_to = parse_date(request.args.get("date_to", ""))
    sanctions = _sanctioned_students_query(user, search, date_from, date_to)
    rows = []
    seen = set()
    for s in sanctions:
        if s.student_id in seen:
            continue
        seen.add(s.student_id)
        rows.append({
            "student": s.student,
            "nb_sanctions": Sanction.query.filter_by(student_id=s.student_id).count(),
            "absence_hours": _absence_hours(s.student_id),
            "last_sanction": s,
        })
    wb_io = sanctions_workbook(rows)
    return send_file(wb_io, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name="LTT_eleves_sanctionnes.xlsx")


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


def _compute_indicators(user, term, department_id=None, class_ids=None, subject_ids=None, course_id=None):
    from models import TeacherIndicator, Teacher, Course, CustomIndicatorType, CustomIndicatorValue
    scoped_dept_ids = user_scoped_department_ids(user) if user.role == "censeur" else None
    teachers_q = Teacher.query
    if scoped_dept_ids is not None:
        teachers_q = teachers_q.filter(Teacher.department_id.in_(scoped_dept_ids))
    teachers = teachers_q.all()
    teacher_ids = [t.id for t in teachers]
    courses_q = Course.query.join(SchoolClass).filter(Course.teacher_id.in_(teacher_ids)) if teacher_ids else None
    if courses_q is not None and department_id:
        courses_q = courses_q.filter(SchoolClass.department_id == department_id)
    if courses_q is not None and class_ids:
        courses_q = courses_q.filter(Course.class_id.in_(class_ids))
    if courses_q is not None and subject_ids:
        courses_q = courses_q.filter(Course.subject_id.in_(subject_ids))
    if courses_q is not None and course_id:
        courses_q = courses_q.filter(Course.id == course_id)
    courses = [course for course in (courses_q.all() if courses_q is not None else [])
               if not is_timetable_only_subject(course.subject)]
    if user.role == "censeur" and user.section_id is None:
        # Censeur Enseignements Généraux : uniquement ses propres matières, quelle que soit la section
        courses = [c for c in courses if c.subject.category == "Enseignements Généraux"]
    inds = {i.course_id: i for i in TeacherIndicator.query.filter(
        TeacherIndicator.teacher_id.in_(teacher_ids), TeacherIndicator.term == term).all()} if teacher_ids else {}

    custom_types_q = CustomIndicatorType.query
    if user.role == "censeur" and user.section_id:
        custom_types_q = custom_types_q.filter(db.or_(CustomIndicatorType.section_id == user.section_id,
                                                        CustomIndicatorType.section_id.is_(None)))
    custom_types = custom_types_q.order_by(CustomIndicatorType.label).all()
    custom_values_by_course = {}
    for ct in custom_types:
        for v in CustomIndicatorValue.query.filter_by(indicator_type_id=ct.id, term=term).all():
            v.pct = _pct(v.done, v.planned)  # attribut transitoire (non persisté), pour l'affichage uniquement
            custom_values_by_course.setdefault(v.course_id, {})[ct.id] = v

    rows = []
    missing = []
    for c in courses:
        ind = inds.get(c.id)
        if not ind:
            missing.append(c)
            continue
        rows.append({
            "teacher": c.teacher, "course": c, "ind": ind,
            "pct_hours": _pct(ind.hours_done, ind.hours_due),
            "pct_lessons": _pct(ind.lessons_done, ind.lessons_planned),
            "pct_digital_lessons": _pct(ind.digital_lessons_done, ind.digital_lessons_planned),
            "pct_tp": _pct(ind.tp_done, ind.tp_planned),
            "pct_digital_tp": _pct(ind.digital_tp_done, ind.digital_tp_planned),
            "custom": custom_values_by_course.get(c.id, {}),
        })
    rows.sort(key=lambda r: (r["teacher"].user.full_name, r["course"].school_class.name))
    totals = {k: sum(r["ind"].__getattribute__(k) for r in rows) for k in
              ["hours_due", "hours_done", "lessons_planned", "lessons_done",
               "digital_lessons_planned", "digital_lessons_done",
               "tp_planned", "tp_done", "digital_tp_planned", "digital_tp_done"]}
    totals["pct_hours"] = _pct(totals["hours_done"], totals["hours_due"])
    totals["pct_lessons"] = _pct(totals["lessons_done"], totals["lessons_planned"])
    totals["pct_digital_lessons"] = _pct(totals["digital_lessons_done"], totals["digital_lessons_planned"])
    totals["pct_tp"] = _pct(totals["tp_done"], totals["tp_planned"])
    totals["pct_digital_tp"] = _pct(totals["digital_tp_done"], totals["digital_tp_planned"])
    return rows, totals, missing, custom_types


@app.route("/censeur/indicateurs")
@roles_required("censeur", "censeur_crm", "directeur")
def censeur_indicators():
    user = User.query.get(session["user_id"])
    term = request.args.get("term", TERMS[0])
    view = request.args.get("view", "cours")
    sequence = request.args.get("sequence", type=int)
    department_id = request.args.get("department_id", type=int)
    class_id = request.args.get("class_id", type=int)
    class_ids = list(dict.fromkeys(request.args.getlist("class_ids", type=int)))
    if class_id and class_id not in class_ids:
        class_ids.append(class_id)
    subject_ids = list(dict.fromkeys(request.args.getlist("subject_ids", type=int)))
    course_id = request.args.get("course_id", type=int)
    assessment_id = request.args.get("assessment_id", type=int)
    valid_sequences = TERM_SEQUENCES.get(term, ())
    if sequence not in valid_sequences:
        sequence = None
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    scoped_dept_ids = user_scoped_department_ids(user) if user.role == "censeur" else None
    departments_q = Department.query.order_by(Department.name)
    if scoped_dept_ids is not None:
        departments_q = departments_q.filter(Department.id.in_(scoped_dept_ids))
    available_departments = departments_q.all()
    if department_id and department_id not in {item.id for item in available_departments}:
        abort(403)
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    if department_id:
        classes_q = classes_q.filter(SchoolClass.department_id == department_id)
    scoped_classes = sort_classes_by_level(classes_q.all())
    if any(item_id not in {item.id for item in scoped_classes} for item_id in class_ids):
        abort(403)
    subjects_q = Subject.query.order_by(Subject.name)
    if scoped_dept_ids is not None:
        subjects_q = subjects_q.filter(Subject.department_id.in_(scoped_dept_ids))
    if department_id:
        subjects_q = subjects_q.filter(Subject.department_id == department_id)
    available_subjects = [subject for subject in subjects_q.all() if not is_timetable_only_subject(subject)]
    if any(item_id not in {item.id for item in available_subjects} for item_id in subject_ids):
        abort(403)
    courses_q = Course.query.join(SchoolClass)
    if scoped_class_ids is not None:
        courses_q = courses_q.filter(Course.class_id.in_(scoped_class_ids))
    if department_id:
        courses_q = courses_q.filter(SchoolClass.department_id == department_id)
    if class_ids:
        courses_q = courses_q.filter(Course.class_id.in_(class_ids))
    if subject_ids:
        courses_q = courses_q.filter(Course.subject_id.in_(subject_ids))
    if course_id:
        courses_q = courses_q.filter(Course.id == course_id)
    scoped_courses = [course for course in courses_q.order_by(SchoolClass.name).all()
                      if not is_timetable_only_subject(course.subject)]
    if course_id and not scoped_courses:
        abort(403)
    rows, totals, missing, custom_types = _compute_indicators(
        user, term, department_id=department_id, class_ids=class_ids, subject_ids=subject_ids, course_id=course_id
    )
    assessments_q = PlannedAssessment.query.join(Course).join(SchoolClass).filter(PlannedAssessment.term == term)
    if scoped_class_ids is not None:
        assessments_q = assessments_q.filter(Course.class_id.in_(scoped_class_ids))
    if department_id:
        assessments_q = assessments_q.filter(SchoolClass.department_id == department_id)
    if class_ids:
        assessments_q = assessments_q.filter(Course.class_id.in_(class_ids))
    if subject_ids:
        assessments_q = assessments_q.filter(Course.subject_id.in_(subject_ids))
    if course_id:
        assessments_q = assessments_q.filter(Course.id == course_id)
    if sequence:
        assessments_q = assessments_q.filter(PlannedAssessment.sequence == sequence)
    if assessment_id:
        assessments_q = assessments_q.filter(PlannedAssessment.id == assessment_id)
    evaluation_rows = []
    for assessment in assessments_q.order_by(PlannedAssessment.scheduled_date).all():
        if is_timetable_only_subject(assessment.course.subject):
            continue
        grades = Grade.query.filter_by(course_id=assessment.course_id, term=assessment.term,
                                       type="Évaluation", sequence=assessment.sequence).all()
        values = [grade.value / grade.max_value * 20 if grade.max_value else grade.value for grade in grades]
        evaluation_rows.append({
            "assessment": assessment, "expected": len(assessment.course.school_class.students),
            "submitted": len({grade.student_id for grade in grades}),
            "average": round(sum(values) / len(values), 1) if values else None,
            "success_rate": round(sum(value >= 10 for value in values) / len(values) * 100) if values else None,
        })
    evaluation_totals = {
        "planned": len(evaluation_rows), "expected": sum(row["expected"] for row in evaluation_rows),
        "submitted": sum(row["submitted"] for row in evaluation_rows),
    }
    averages = [row["average"] for row in evaluation_rows if row["average"] is not None]
    evaluation_totals["average"] = round(sum(averages) / len(averages), 1) if averages else None
    evaluation_totals["submission_rate"] = round(evaluation_totals["submitted"] / evaluation_totals["expected"] * 100) if evaluation_totals["expected"] else 0
    available_assessments_q = PlannedAssessment.query.join(Course).join(SchoolClass).filter(PlannedAssessment.term == term)
    if scoped_class_ids is not None:
        available_assessments_q = available_assessments_q.filter(Course.class_id.in_(scoped_class_ids))
    if department_id:
        available_assessments_q = available_assessments_q.filter(SchoolClass.department_id == department_id)
    if class_ids:
        available_assessments_q = available_assessments_q.filter(Course.class_id.in_(class_ids))
    if subject_ids:
        available_assessments_q = available_assessments_q.filter(Course.subject_id.in_(subject_ids))
    if course_id:
        available_assessments_q = available_assessments_q.filter(Course.id == course_id)
    if sequence:
        available_assessments_q = available_assessments_q.filter(PlannedAssessment.sequence == sequence)
    available_assessments = [assessment for assessment in available_assessments_q.order_by(PlannedAssessment.scheduled_date).all()
                             if not is_timetable_only_subject(assessment.course.subject)]
    by_dept = None
    if view == "departement":
        by_dept = {}
        for r in rows:
            d = r["course"].school_class.department
            key = d.id if d else None
            entry = by_dept.setdefault(key, {"department": d, "hours_due": 0, "hours_done": 0,
                                              "lessons_planned": 0, "lessons_done": 0,
                                              "digital_lessons_planned": 0, "digital_lessons_done": 0,
                                              "tp_planned": 0, "tp_done": 0,
                                              "digital_tp_planned": 0, "digital_tp_done": 0})
            for f in ["hours_due", "hours_done", "lessons_planned", "lessons_done",
                      "digital_lessons_planned", "digital_lessons_done",
                      "tp_planned", "tp_done", "digital_tp_planned", "digital_tp_done"]:
                entry[f] += getattr(r["ind"], f)
        for entry in by_dept.values():
            entry["pct_hours"] = _pct(entry["hours_done"], entry["hours_due"])
            entry["pct_lessons"] = _pct(entry["lessons_done"], entry["lessons_planned"])
            entry["pct_digital_lessons"] = _pct(entry["digital_lessons_done"], entry["digital_lessons_planned"])
            entry["pct_tp"] = _pct(entry["tp_done"], entry["tp_planned"])
            entry["pct_digital_tp"] = _pct(entry["digital_tp_done"], entry["digital_tp_planned"])
        by_dept = sorted(by_dept.values(), key=lambda e: e["department"].name if e["department"] else "")

    return render_template("censeur_indicators.html", rows=rows, totals=totals, term=term, terms=TERMS,
                            missing=missing, view=view, by_dept=by_dept, custom_types=custom_types,
                            sequence=sequence, valid_sequences=valid_sequences, class_id=class_id, class_ids=class_ids,
                            course_id=course_id, assessment_id=assessment_id, scoped_classes=scoped_classes,
                            scoped_courses=scoped_courses, available_subjects=available_subjects,
                            subject_ids=subject_ids, available_assessments=available_assessments,
                            evaluation_rows=evaluation_rows, evaluation_totals=evaluation_totals,
                            department_id=department_id, available_departments=available_departments)


@app.route("/censeur/indicateurs/export.xlsx")
@roles_required("censeur", "censeur_crm", "directeur")
def censeur_indicators_export():
    from flask import send_file
    from excel_utils import indicators_workbook
    user = User.query.get(session["user_id"])
    term = request.args.get("term", TERMS[0])
    department_id = request.args.get("department_id", type=int)
    class_id = request.args.get("class_id", type=int)
    class_ids = list(dict.fromkeys(request.args.getlist("class_ids", type=int)))
    if class_id and class_id not in class_ids:
        class_ids.append(class_id)
    subject_ids = list(dict.fromkeys(request.args.getlist("subject_ids", type=int)))
    course_id = request.args.get("course_id", type=int)
    scoped_dept_ids = user_scoped_department_ids(user) if user.role == "censeur" else None
    if department_id:
        department = Department.query.get_or_404(department_id)
        if scoped_dept_ids is not None and department.id not in scoped_dept_ids:
            abort(403)
    rows, totals, missing, custom_types = _compute_indicators(
        user, term, department_id=department_id, class_ids=class_ids, subject_ids=subject_ids, course_id=course_id
    )
    wb_io = indicators_workbook(rows, totals, term, custom_types)
    filename = f"LTT_indicateurs_{term}.xlsx".replace(" ", "_")
    return send_file(wb_io, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name=filename)


@app.route("/censeur/indicateurs/<int:course_id>/modifier", methods=["POST"])
@roles_required("censeur", "directeur")
def censeur_indicator_edit(course_id):
    from models import TeacherIndicator, Course
    user = User.query.get(session["user_id"])
    course = Course.query.get_or_404(course_id)
    teacher = course.teacher
    scoped_dept_ids = user_scoped_department_ids(user) if user.role == "censeur" else None
    if scoped_dept_ids is not None and teacher.department_id not in scoped_dept_ids:
        abort(403)
    term = request.form.get("term", TERMS[0])
    ind = TeacherIndicator.query.filter_by(course_id=course.id, term=term).first()
    if not ind:
        ind = TeacherIndicator(teacher_id=teacher.id, course_id=course.id, term=term)
        db.session.add(ind)
    for field in ["hours_due", "hours_done", "lessons_planned", "lessons_done",
                  "digital_lessons_planned", "digital_lessons_done",
                  "tp_planned", "tp_done", "digital_tp_planned", "digital_tp_done"]:
        setattr(ind, field, request.form.get(field, 0, type=int))
    db.session.commit()
    flash(f"Indicateurs de {teacher.user.full_name} ({course.school_class.name} — {course.subject.name}) enregistrés.", "success")
    return redirect(url_for("censeur_indicators", term=term))


@app.route("/censeur/conseil-de-classe/statistiques")
@roles_required("censeur", "censeur_crm", "directeur")
def censeur_council_stats():
    user = User.query.get(session["user_id"])
    term = request.args.get("term", TERMS[0])
    sequence = request.args.get("sequence", type=int)
    if sequence not in TERM_SEQUENCES.get(term, ()):
        sequence = None
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    scoped_dept_ids = user_scoped_department_ids(user) if user.role == "censeur" else None
    subject_category = "Enseignements Généraux" if (user.role == "censeur" and user.section_id is None) else None
    department_id = request.args.get("department_id", type=int)
    departments_q = Department.query.order_by(Department.name)
    if scoped_dept_ids is not None:
        departments_q = departments_q.filter(Department.id.in_(scoped_dept_ids))
    available_departments = departments_q.all()
    if department_id and department_id not in {item.id for item in available_departments}:
        abort(403)
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    if department_id:
        classes_q = classes_q.filter(SchoolClass.department_id == department_id)
    available_classes = sort_classes_by_level(classes_q.all())
    class_id = request.args.get("class_id", type=int)
    class_ids = list(dict.fromkeys(request.args.getlist("class_ids", type=int)))
    if class_id and class_id not in class_ids:
        class_ids.append(class_id)
    subject_ids = list(dict.fromkeys(request.args.getlist("subject_ids", type=int)))
    course_id = request.args.get("course_id", type=int)
    if any(item_id not in {item.id for item in available_classes} for item_id in class_ids):
        abort(403)
    subjects_q = Subject.query.order_by(Subject.name)
    if scoped_dept_ids is not None:
        subjects_q = subjects_q.filter(Subject.department_id.in_(scoped_dept_ids))
    if department_id:
        subjects_q = subjects_q.filter(Subject.department_id == department_id)
    if class_ids:
        subjects_q = subjects_q.join(Course).filter(Course.class_id.in_(class_ids)).distinct()
    available_subjects = [subject for subject in subjects_q.all() if not is_timetable_only_subject(subject)]
    if any(item_id not in {item.id for item in available_subjects} for item_id in subject_ids):
        abort(403)
    courses_q = Course.query.join(SchoolClass)
    if scoped_class_ids is not None:
        courses_q = courses_q.filter(Course.class_id.in_(scoped_class_ids))
    if department_id:
        courses_q = courses_q.filter(SchoolClass.department_id == department_id)
    if class_ids:
        courses_q = courses_q.filter(Course.class_id.in_(class_ids))
    subject_courses = [course for course in courses_q.all()
                       if not is_timetable_only_subject(course.subject)]
    subject_class_ids = {}
    for item in subject_courses:
        subject_class_ids.setdefault(item.subject_id, set()).add(item.class_id)
    if subject_ids:
        courses_q = courses_q.filter(Course.subject_id.in_(subject_ids))
    available_courses = [course for course in courses_q.order_by(SchoolClass.name).all()
                         if not is_timetable_only_subject(course.subject)]
    if course_id:
        selected_course = next((item for item in available_courses if item.id == course_id), None)
        if not selected_course:
            abort(403)
        class_id = selected_course.class_id
    classes = [item for item in available_classes if not class_ids or item.id in class_ids]
    stats = council_statistics(classes, term, subject_category=subject_category, sequence=sequence,
                               course_id=course_id, subject_ids=subject_ids)
    return render_template("censeur_council_stats.html", stats=stats, term=term, terms=TERMS,
                           sequence=sequence, valid_sequences=TERM_SEQUENCES.get(term, ()),
                           class_id=class_id, class_ids=class_ids, course_id=course_id,
                           available_classes=available_classes, available_courses=available_courses,
                           department_id=department_id, available_departments=available_departments,
                           subject_ids=subject_ids, available_subjects=available_subjects,
                           subject_class_ids={key: sorted(value) for key, value in subject_class_ids.items()})


@app.route("/censeur/conseil-de-classe/statistiques/export.xlsx")
@roles_required("censeur", "censeur_crm", "directeur")
def censeur_council_stats_export():
    from flask import send_file
    from excel_utils import council_stats_workbook
    user = User.query.get(session["user_id"])
    term = request.args.get("term", TERMS[0])
    sequence = request.args.get("sequence", type=int)
    if sequence not in TERM_SEQUENCES.get(term, ()):
        sequence = None
    scoped_class_ids = user_scoped_class_ids(user) if user.role == "censeur" else None
    scoped_dept_ids = user_scoped_department_ids(user) if user.role == "censeur" else None
    subject_category = "Enseignements Généraux" if (user.role == "censeur" and user.section_id is None) else None
    department_id = request.args.get("department_id", type=int)
    departments_q = Department.query.order_by(Department.name)
    if scoped_dept_ids is not None:
        departments_q = departments_q.filter(Department.id.in_(scoped_dept_ids))
    available_departments = departments_q.all()
    if department_id and department_id not in {item.id for item in available_departments}:
        abort(403)
    classes_q = SchoolClass.query.join(Department).order_by(Department.name, SchoolClass.level)
    if scoped_class_ids is not None:
        classes_q = classes_q.filter(SchoolClass.id.in_(scoped_class_ids))
    if department_id:
        classes_q = classes_q.filter(SchoolClass.department_id == department_id)
    available_classes = sort_classes_by_level(classes_q.all())
    class_id = request.args.get("class_id", type=int)
    class_ids = list(dict.fromkeys(request.args.getlist("class_ids", type=int)))
    if class_id and class_id not in class_ids:
        class_ids.append(class_id)
    subject_ids = list(dict.fromkeys(request.args.getlist("subject_ids", type=int)))
    course_id = request.args.get("course_id", type=int)
    if any(item_id not in {item.id for item in available_classes} for item_id in class_ids):
        abort(403)
    subjects_q = Subject.query.order_by(Subject.name)
    if scoped_dept_ids is not None:
        subjects_q = subjects_q.filter(Subject.department_id.in_(scoped_dept_ids))
    if department_id:
        subjects_q = subjects_q.filter(Subject.department_id == department_id)
    if class_ids:
        subjects_q = subjects_q.join(Course).filter(Course.class_id.in_(class_ids)).distinct()
    available_subjects = [subject for subject in subjects_q.all() if not is_timetable_only_subject(subject)]
    if any(item_id not in {item.id for item in available_subjects} for item_id in subject_ids):
        abort(403)
    courses_q = Course.query.join(SchoolClass)
    if scoped_class_ids is not None:
        courses_q = courses_q.filter(Course.class_id.in_(scoped_class_ids))
    if department_id:
        courses_q = courses_q.filter(SchoolClass.department_id == department_id)
    if class_ids:
        courses_q = courses_q.filter(Course.class_id.in_(class_ids))
    if subject_ids:
        courses_q = courses_q.filter(Course.subject_id.in_(subject_ids))
    available_courses = courses_q.all()
    if course_id:
        selected_course = next((item for item in available_courses if item.id == course_id), None)
        if not selected_course:
            abort(403)
        class_id = selected_course.class_id
    classes = [item for item in available_classes if not class_ids or item.id in class_ids]
    stats = council_statistics(classes, term, subject_category=subject_category, sequence=sequence,
                               course_id=course_id, subject_ids=subject_ids)
    wb_io = council_stats_workbook(stats, term)
    suffix = f"_sequence_{sequence}" if sequence else ""
    if department_id:
        suffix += f"_departement_{department_id}"
    if course_id:
        suffix += f"_cours_{course_id}"
    filename = f"LTT_fiche_statistique_{term}{suffix}.xlsx".replace(" ", "_")
    return send_file(wb_io, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name=filename)


@app.route("/censeur/indicateurs/types/nouveau", methods=["POST"])
@roles_required("censeur", "directeur")
def censeur_indicator_type_new():
    from models import CustomIndicatorType
    user = User.query.get(session["user_id"])
    label = request.form.get("label", "").strip()
    unit_planned = request.form.get("unit_planned", "Prévu").strip() or "Prévu"
    unit_done = request.form.get("unit_done", "Fait").strip() or "Fait"
    if not label:
        flash("Le libellé de l'indicateur est obligatoire.", "warning")
        return redirect(url_for("censeur_indicators"))
    it = CustomIndicatorType(label=label, unit_planned=unit_planned, unit_done=unit_done,
                              section_id=user.section_id if user.role == "censeur" else None,
                              created_by_id=user.id)
    db.session.add(it)
    db.session.commit()
    flash(f"Indicateur « {label} » créé — il apparaîtra chez les enseignants concernés.", "success")
    return redirect(url_for("censeur_indicators"))


@app.route("/censeur/indicateurs/types/<int:type_id>/supprimer")
@roles_required("censeur", "directeur")
def censeur_indicator_type_delete(type_id):
    from models import CustomIndicatorType
    user = User.query.get(session["user_id"])
    it = CustomIndicatorType.query.get_or_404(type_id)
    if user.role == "censeur" and it.section_id != user.section_id:
        abort(403)
    label = it.label
    db.session.delete(it)
    db.session.commit()
    flash(f"Indicateur « {label} » supprimé.", "info")
    return redirect(url_for("censeur_indicators"))
