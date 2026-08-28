from flask import render_template, request, abort, session, url_for, send_file
from app import app, db
from models import User, Grade, Attendance, ScheduleEntry, Course, Sanction, Reward, Student, BulletinApproval
from utils import roles_required, general_average, subject_averages, bulletin_data, DAYS, TERMS


def current_student():
    user = User.query.get(session["user_id"])
    return user.student_profile


@app.route("/eleve/notes")
@roles_required("eleve")
def student_grades():
    student = current_student()
    if not student:
        abort(403)
    term = request.args.get("term", TERMS[0])
    rows = subject_averages(student.id, term=term)
    return render_template("student_grades.html", student=student, rows=rows, term=term, terms=TERMS)


@app.route("/eleve/emploi-du-temps")
@roles_required("eleve")
def student_schedule():
    student = current_student()
    if not student.class_id:
        abort(403)
    entries = ScheduleEntry.query.join(Course).filter(Course.class_id == student.class_id,
                                                        ScheduleEntry.published == True).all()  # noqa: E712
    grid = {d: [] for d in DAYS}
    for e in entries:
        grid[e.day].append(e)
    for d in grid:
        grid[d].sort(key=lambda e: e.start_time)
    return render_template("student_schedule.html", grid=grid, days=DAYS, student=student)


@app.route("/eleve/absences")
@roles_required("eleve")
def student_absences_self():
    student = current_student()
    records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).all()
    return render_template("student_absences.html", student=student, records=records)


@app.route("/eleve/bulletin")
@roles_required("eleve")
def student_bulletin_self():
    student = current_student()
    return _render_bulletin(student, viewer="eleve")


@app.route("/eleves/<int:student_id>/bulletin")
@roles_required("directeur", "censeur", "conseiller_orientation")
def student_bulletin_staff(student_id):
    student = Student.query.get_or_404(student_id)
    return _render_bulletin(student, viewer="staff")


@app.route("/eleves/<int:student_id>/bulletin/telecharger")
@roles_required("censeur")
def student_bulletin_pdf_staff(student_id):
    student = Student.query.get_or_404(student_id)
    return _bulletin_pdf_response(student)


@app.route("/eleves/<int:student_id>/bulletin/telecharger.xlsx")
@roles_required("censeur")
def student_bulletin_xlsx_staff(student_id):
    student = Student.query.get_or_404(student_id)
    return _bulletin_xlsx_response(student)


def _bulletin_pdf_response(student, term=None):
    from pdf_utils import render_pdf, student_photo_pdf_path
    from utils import TERMS as T, TERM_SEQUENCES, TERM_ORDINALS
    term = term or request.args.get("term", T[0])
    data = bulletin_data(student, term=term)
    approval = BulletinApproval.query.filter_by(class_id=student.class_id, term=term, status="Validé").first()
    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
    bulletin_ref = f"{student.matricule}-T{T.index(term)+1}-2025"
    pdf = render_pdf("pdf/bulletin_pdf.html", student=student, data=data, term=term,
                      TERM_SEQ_A=seq_a, TERM_SEQ_B=seq_b, term_ordinal=TERM_ORDINALS.get(term, ""),
                      bulletin_ref=bulletin_ref, approval=approval,
                      student_photo_path=student_photo_pdf_path(student.photo))
    if not pdf:
        abort(500)
    filename = f"Bulletin_{student.last_name}_{student.first_name}_{term}.pdf".replace(" ", "_")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


def _bulletin_xlsx_response(student, term=None):
    from excel_utils import bulletin_workbook
    from utils import TERMS as T
    term = term or request.args.get("term", T[0])
    data = bulletin_data(student, term=term)
    wb_io = bulletin_workbook(student, data, term)
    filename = f"Bulletin_{student.last_name}_{student.first_name}_{term}.xlsx".replace(" ", "_")
    return send_file(wb_io, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name=filename)


def _render_bulletin(student, term=None, viewer="eleve"):
    from utils import TERM_SEQUENCES, TERM_ORDINALS
    term = term or request.args.get("term", TERMS[0])
    if viewer == "eleve":
        return render_template("bulletin_awaiting_validation.html", student=student, term=term,
                               notes_url=url_for("student_grades", term=term))
    elif viewer == "parent":
        return render_template("bulletin_awaiting_validation.html", student=student, term=term,
                               notes_url=url_for("parent_child_detail", student_id=student.id, term=term))
    data = bulletin_data(student, term=term)
    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
    bulletin_ref = f"{student.matricule}-T{TERMS.index(term)+1}-2025"
    can_export = False
    if viewer == "staff":
        can_export = session.get("role") == "censeur"
        download_url = url_for("student_bulletin_pdf_staff", student_id=student.id, term=term) if can_export else None
        download_xlsx_url = url_for("student_bulletin_xlsx_staff", student_id=student.id, term=term) if can_export else None
        back_url = url_for("student_detail", student_id=student.id)
    else:
        # Élève et Parent : consultation uniquement, aucune impression ni export.
        download_url = None
        download_xlsx_url = None
        back_url = None
    return render_template("bulletin.html", student=student, data=data, term=term, terms=TERMS,
                            download_url=download_url, download_xlsx_url=download_xlsx_url, back_url=back_url,
                            viewer=viewer, can_export=can_export, TERM_SEQ_A=seq_a, TERM_SEQ_B=seq_b,
                            term_ordinal=TERM_ORDINALS.get(term, ""), bulletin_ref=bulletin_ref)
