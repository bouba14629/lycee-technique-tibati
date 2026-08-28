import os
from datetime import date

os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app
from models import Attendance, Correspondence, CorrespondenceReceipt, Course, Department, Parent, SchoolClass, Section, Student, Subject, Teacher, User, db
from utils import dashboard_alerts


def add_user(username, full_name, role):
    user = User(username=username, full_name=full_name, role=role, active=True)
    user.set_password("Test#2026")
    db.session.add(user)
    db.session.flush()
    return user


def switch_user(client, user):
    with client.session_transaction() as session:
        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role


with app.app_context():
    db.drop_all()
    db.create_all()
    director = add_user("proviseur.test", "Proviseur Test", "directeur")
    supervisor = add_user("surveillant.test", "Surveillant Test", "surveillant_general")
    censeur = add_user("censeur.test", "Censeur Test", "censeur")
    teacher_user = add_user("enseignant.test", "Enseignant Test", "enseignant")
    student_user = add_user("eleve.test", "Élève Test", "eleve")
    parent_user = add_user("parent.test", "Parent Test", "parent")
    section = Section(name="Section Test", code="ST")
    db.session.add(section)
    db.session.flush()
    department = Department(name="Département Test", code="DT", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Classe Test", level="Test", department_id=department.id)
    subject = Subject(name="Matière Test", department_id=department.id)
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
    db.session.add_all([school_class, subject, teacher])
    db.session.flush()
    db.session.add(Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id))
    student = Student(user_id=student_user.id, class_id=school_class.id, matricule="LTT-TEST-001", first_name="Élève", last_name="Test")
    parent = Parent(user_id=parent_user.id, phone="690000000")
    db.session.add_all([student, parent])
    db.session.flush()
    student.parents.append(parent)
    db.session.commit()

    with app.test_client() as client:
        switch_user(client, director)
        create_entry = client.post("/vie-scolaire/carnet/nouveau", data={
            "student_id": student.id, "category": "Discipline", "priority": "Critique",
            "subject": "Retard répété", "body": "Merci de prendre connaissance de ce suivi.",
        }, follow_redirects=False)
        if create_entry.status_code != 302:
            print("CORRESPONDENCE_CREATE_FAILURE", create_entry.status_code, create_entry.data.decode("utf-8", errors="replace")[:1200])
        assert create_entry.status_code == 302
        entry = Correspondence.query.one()
        assert CorrespondenceReceipt.query.filter_by(correspondence_id=entry.id).count() == 2

        switch_user(client, teacher_user)
        assert client.get("/vie-scolaire/carnet/nouveau").status_code == 200
        teacher_entry = client.post("/vie-scolaire/carnet/nouveau", data={
            "student_id": student.id, "category": "Travail scolaire", "priority": "Normale",
            "subject": "Travail à compléter", "body": "Merci de terminer l’exercice demandé.",
        }, follow_redirects=False)
        assert teacher_entry.status_code == 302

        switch_user(client, student_user)
        assert client.get("/vie-scolaire/carnet").status_code == 200
        assert client.get(f"/vie-scolaire/carnet/{entry.id}").status_code == 200
        assert client.get("/vie-scolaire/retards").status_code == 403

        switch_user(client, parent_user)
        inbox = client.get("/vie-scolaire/carnet")
        assert inbox.status_code == 200 and b"Retard r" in inbox.data
        assert client.get("/vie-scolaire/retards").status_code == 403
        view = client.get(f"/vie-scolaire/carnet/{entry.id}")
        assert view.status_code == 200
        receipt = CorrespondenceReceipt.query.filter_by(correspondence_id=entry.id, user_id=parent_user.id).one()
        assert receipt.read_at is not None
        acknowledgement = client.post(f"/vie-scolaire/carnet/{entry.id}/accuser", follow_redirects=False)
        assert acknowledgement.status_code == 302
        assert receipt.acknowledged_at is not None

        switch_user(client, supervisor)
        assert client.get("/vie-scolaire/carnet").status_code == 200
        assert client.get("/vie-scolaire/retards").status_code == 200
        late = client.post("/vie-scolaire/retards/nouveau", data={
            "student_id": student.id, "date": date.today().isoformat(), "arrival_time": "08:20", "reason": "Transport",
        }, follow_redirects=False)
        assert late.status_code == 302
        record = Attendance.query.filter_by(student_id=student.id, type="Retard").one()
        assert record.recorded_by_id == supervisor.id and not record.justified

        switch_user(client, parent_user)
        justification = client.post(f"/vie-scolaire/retards/{record.id}/justifier", data={
            "justification_note": "Panne de transport attestée.",
        }, follow_redirects=False)
        assert justification.status_code == 302
        assert record.justification_requested_at is not None

        switch_user(client, censeur)
        assert client.get("/vie-scolaire/carnet").status_code == 200
        assert client.get("/vie-scolaire/retards").status_code == 200
        validation = client.get(f"/vie-scolaire/retards/{record.id}/valider", follow_redirects=False)
        assert validation.status_code == 302
        assert record.justified and record.justified_by_id == censeur.id

        db.session.add_all([
            Attendance(date=date.today(), start_time="08:30", type="Retard", student_id=student.id, recorded_by_id=supervisor.id),
            Attendance(date=date.today(), start_time="08:40", type="Retard", student_id=student.id, recorded_by_id=supervisor.id),
        ])
        db.session.commit()
        assert any(alert[2] == "Retards répétés" for alert in dashboard_alerts())

        switch_user(client, director)
        assert client.get("/vie-scolaire/carnet").status_code == 200
        assert client.get("/vie-scolaire/carnet/nouveau").status_code == 200
        assert client.get("/vie-scolaire/retards").status_code == 200

        switch_user(client, teacher_user)
        assert client.get("/vie-scolaire/carnet").status_code == 200
        assert client.get("/vie-scolaire/retards").status_code == 403

print("LIFE_SCHOOL_FEATURE_TEST_OK")
