from datetime import date, datetime, timedelta

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import app
from models import Attendance, Correspondence, CorrespondenceReceipt, Student, User, db
from utils import login_required, notify, roles_required, user_scoped_class_ids


STAFF_WRITERS = ("directeur", "censeur", "surveillant_general", "conseiller_orientation", "enseignant")
LIFE_SCHOOL_MANAGERS = ("directeur", "censeur", "surveillant_general", "conseiller_orientation")


def _current_user():
    return User.query.get_or_404(session["user_id"])


def _writer_students(user):
    query = Student.query
    if user.role == "enseignant" and user.teacher_profile:
        class_ids = [course.class_id for course in user.teacher_profile.courses]
        query = query.filter(Student.class_id.in_(class_ids or [-1]))
    elif user.role in LIFE_SCHOOL_MANAGERS:
        class_ids = user_scoped_class_ids(user)
        if class_ids is not None:
            query = query.filter(Student.class_id.in_(class_ids or [-1]))
    return query.order_by(Student.last_name, Student.first_name).all()


def _can_read_entry(user, entry):
    if user.role in ("directeur", "censeur", "surveillant_general", "conseiller_orientation") or entry.author_id == user.id:
        return True
    return CorrespondenceReceipt.query.filter_by(correspondence_id=entry.id, user_id=user.id).first() is not None


@app.route("/vie-scolaire/carnet")
@login_required
def correspondence_inbox():
    user = _current_user()
    if user.role in LIFE_SCHOOL_MANAGERS:
        entries = Correspondence.query.order_by(Correspondence.created_at.desc()).all()
    elif user.role in STAFF_WRITERS:
        entries = Correspondence.query.filter_by(author_id=user.id).order_by(Correspondence.created_at.desc()).all()
    else:
        receipt_ids = db.session.query(CorrespondenceReceipt.correspondence_id).filter_by(user_id=user.id)
        entries = Correspondence.query.filter(Correspondence.id.in_(receipt_ids)).order_by(Correspondence.created_at.desc()).all()
    receipts = {receipt.correspondence_id: receipt for receipt in CorrespondenceReceipt.query.filter_by(user_id=user.id).all()}
    return render_template("correspondence.html", entries=entries, receipts=receipts, can_write=user.role in STAFF_WRITERS)


@app.route("/vie-scolaire/carnet/nouveau", methods=["GET", "POST"])
@roles_required(*STAFF_WRITERS)
def correspondence_new():
    user = _current_user()
    students = _writer_students(user)
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        category = request.form.get("category", "Information")
        priority = request.form.get("priority", "Normale")
        student = next((item for item in students if item.id == student_id), None)
        if not (student and subject and body):
            flash("Choisissez un élève et renseignez l’objet ainsi que le message.", "warning")
        else:
            entry = Correspondence(author_id=user.id, student_id=student.id, category=category, priority=priority,
                                   subject=subject, body=body)
            db.session.add(entry)
            db.session.flush()
            recipients = {student.user_id} if student.user_id else set()
            recipients.update(parent.user_id for parent in student.parents if parent.user_id)
            for recipient_id in recipients:
                db.session.add(CorrespondenceReceipt(correspondence_id=entry.id, user_id=recipient_id))
                notify(recipient_id, f"Carnet numérique : {subject}", link=url_for("correspondence_view", entry_id=entry.id))
            db.session.commit()
            flash("Message ajouté au carnet et transmis aux responsables concernés.", "success")
            return redirect(url_for("correspondence_view", entry_id=entry.id))
    return render_template("correspondence_new.html", students=students)


@app.route("/vie-scolaire/carnet/<int:entry_id>")
@login_required
def correspondence_view(entry_id):
    user = _current_user()
    entry = Correspondence.query.get_or_404(entry_id)
    if not _can_read_entry(user, entry):
        abort(403)
    receipt = CorrespondenceReceipt.query.filter_by(correspondence_id=entry.id, user_id=user.id).first()
    if receipt and not receipt.read_at:
        receipt.read_at = datetime.utcnow()
        db.session.commit()
    return render_template("correspondence_view.html", entry=entry, receipt=receipt,
                           can_acknowledge=bool(receipt and not receipt.acknowledged_at))


@app.route("/vie-scolaire/carnet/<int:entry_id>/accuser", methods=["POST"])
@login_required
def correspondence_acknowledge(entry_id):
    user = _current_user()
    entry = Correspondence.query.get_or_404(entry_id)
    receipt = CorrespondenceReceipt.query.filter_by(correspondence_id=entry.id, user_id=user.id).first_or_404()
    if not receipt.acknowledged_at:
        receipt.read_at = receipt.read_at or datetime.utcnow()
        receipt.acknowledged_at = datetime.utcnow()
        notify(entry.author_id, f"Accusé de réception du carnet : {entry.student.full_name}",
               link=url_for("correspondence_view", entry_id=entry.id))
        db.session.commit()
        flash("Accusé de réception enregistré.", "success")
    return redirect(url_for("correspondence_view", entry_id=entry.id))


@app.route("/vie-scolaire/retards")
@roles_required(*LIFE_SCHOOL_MANAGERS)
def late_arrivals():
    user = _current_user()
    records_q = Attendance.query.filter_by(type="Retard")
    scoped_classes = user_scoped_class_ids(user)
    if scoped_classes is not None:
        records_q = records_q.join(Student).filter(Student.class_id.in_(scoped_classes or [-1]))
    records = records_q.order_by(Attendance.date.desc(), Attendance.start_time.desc()).all()
    repeated_since = date.today() - timedelta(days=30)
    repeated_students = {record.student_id for record in records if record.date and record.date >= repeated_since}
    return render_template("late_arrivals.html", records=records, repeated_students=repeated_students,
                           can_record=user.role in ("directeur", "surveillant_general"),
                           can_validate=user.role in ("directeur", "censeur", "surveillant_general"))


@app.route("/vie-scolaire/retards/nouveau", methods=["GET", "POST"])
@roles_required("directeur", "surveillant_general")
def late_arrival_new():
    user = _current_user()
    students = _writer_students(user)
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        arrival_time = request.form.get("arrival_time", "").strip()
        reason = request.form.get("reason", "").strip()
        entry_date = request.form.get("date", type=lambda value: datetime.strptime(value, "%Y-%m-%d").date() if value else date.today())
        student = next((item for item in students if item.id == student_id), None)
        if not student or not arrival_time:
            flash("Choisissez un élève et renseignez l’heure d’arrivée.", "warning")
        else:
            record = Attendance(date=entry_date, start_time=arrival_time, type="Retard", reason=reason,
                                student_id=student.id, recorded_by_id=user.id, justified=False)
            db.session.add(record)
            recipient_ids = {student.user_id} if student.user_id else set()
            recipient_ids.update(parent.user_id for parent in student.parents if parent.user_id)
            for recipient_id in recipient_ids:
                notify(recipient_id, f"Retard enregistré : {student.full_name}", link=url_for("late_arrivals"))
            db.session.commit()
            flash("Retard enregistré et responsables notifiés dans l’application.", "success")
            return redirect(url_for("late_arrivals"))
    return render_template("late_arrival_new.html", students=students, today=date.today().isoformat())


@app.route("/vie-scolaire/retards/<int:record_id>/justifier", methods=["GET", "POST"])
@roles_required("parent")
def late_arrival_justify(record_id):
    user = _current_user()
    record = Attendance.query.filter_by(id=record_id, type="Retard").first_or_404()
    if user.parent_profile not in record.student.parents:
        abort(403)
    if request.method == "POST":
        note = request.form.get("justification_note", "").strip()
        if not note:
            flash("Précisez le motif de justification.", "warning")
        else:
            record.justification_note = note
            record.justification_requested_at = datetime.utcnow()
            if record.recorded_by_id:
                notify(record.recorded_by_id, f"Justification de retard à examiner : {record.student.full_name}",
                       link=url_for("late_arrivals"))
            db.session.commit()
            flash("Justification transmise à la vie scolaire.", "success")
            return redirect(url_for("parent_children"))
    return render_template("late_arrival_justify.html", record=record)


@app.route("/vie-scolaire/retards/<int:record_id>/valider")
@roles_required("directeur", "censeur", "surveillant_general")
def late_arrival_validate(record_id):
    user = _current_user()
    record = Attendance.query.filter_by(id=record_id, type="Retard").first_or_404()
    record.justified = True
    record.justified_at = datetime.utcnow()
    record.justified_by_id = user.id
    recipient_ids = {record.student.user_id} if record.student.user_id else set()
    recipient_ids.update(parent.user_id for parent in record.student.parents if parent.user_id)
    for recipient_id in recipient_ids:
        notify(recipient_id, f"Justification de retard validée : {record.student.full_name}", link=url_for("parent_children"))
    db.session.commit()
    flash("Justification de retard validée.", "success")
    return redirect(url_for("late_arrivals"))
