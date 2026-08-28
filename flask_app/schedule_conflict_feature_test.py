import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Course, Department, Room, ScheduleEntry, SchoolClass, Section, Subject, Teacher, User, db


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        principal = User(username="proviseur.test", role="directeur", full_name="Proviseur Test", must_change_password=False)
        principal.set_password("Lyttib")
        teacher_user = User(username="enseignant.test", role="enseignant", full_name="Enseignant Test", must_change_password=False)
        teacher_user.set_password("Lyttib")
        section = Section(name="Section Technique", code="STT")
        db.session.add_all([principal, teacher_user, section])
        db.session.flush()
        department = Department(name="Électrotechnique", code="GEL", section_id=section.id)
        db.session.add(department)
        db.session.flush()
        school_class = SchoolClass(name="2nde GEL", level="2nde", department_id=department.id)
        subject = Subject(name="Électrotechnique", coefficient=2, department_id=department.id)
        teacher = Teacher(user_id=teacher_user.id, department_id=department.id, specialty="Électrotechnique")
        room = Room(name="Atelier GEL", type="Atelier", capacity=30, department_id=department.id)
        db.session.add_all([school_class, subject, teacher, room])
        db.session.commit()
        ids = (school_class.id, subject.id, teacher.id, room.id)

    class_id, subject_id, teacher_id, room_id = ids
    with app.test_client() as client:
        login = client.post("/login", data={"username": "proviseur.test", "password": "Lyttib"})
        assert login.status_code == 302
        created = client.post(f"/censeur/emplois-du-temps?class_id={class_id}", data={
            "subject_id": str(subject_id), "teacher_id": str(teacher_id), "room_id": str(room_id),
            "day": "Lundi", "start_time": "08:00", "end_time": "10:00",
        }, follow_redirects=True)
        assert created.status_code == 200
        with app.app_context():
            assert ScheduleEntry.query.count() == 1
            assert Course.query.count() == 1
        without_room = client.post(f"/censeur/emplois-du-temps?class_id={class_id}", data={
            "subject_id": str(subject_id), "teacher_id": str(teacher_id),
            "day": "Mardi", "start_time": "08:00", "end_time": "10:00",
        }, follow_redirects=True)
        assert without_room.status_code == 200
        assert b"Salle non d" in without_room.data
        with app.app_context():
            optional_entry = ScheduleEntry.query.filter_by(day="Mardi").one()
            assert optional_entry.room_id is None
        official_class = client.get(f"/censeur/emplois-du-temps/{class_id}/officiel")
        assert official_class.status_code == 200
        assert "Électrotechnique".encode() in official_class.data
        official_pdf = client.get(f"/censeur/emplois-du-temps/{class_id}/officiel.pdf")
        assert official_pdf.status_code == 200
        assert "application/pdf" in official_pdf.content_type
        assert official_pdf.data.startswith(b"%PDF")
        with open("/tmp/ltt-schedule-official.pdf", "wb") as handle:
            handle.write(official_pdf.data)
        conflict = client.post(f"/censeur/emplois-du-temps?class_id={class_id}", data={
            "subject_id": str(subject_id), "teacher_id": str(teacher_id), "room_id": str(room_id),
            "day": "Lundi", "start_time": "09:00", "end_time": "11:00",
        }, follow_redirects=True)
        assert conflict.status_code == 200
        assert b"Conflit d" in conflict.data
        assert b"Salle d" in conflict.data
        with app.app_context():
            assert ScheduleEntry.query.count() == 2
        invalid_time = client.post(f"/censeur/emplois-du-temps?class_id={class_id}", data={
            "subject_id": str(subject_id), "teacher_id": str(teacher_id), "room_id": str(room_id),
            "day": "Lundi", "start_time": "11:00", "end_time": "09:00",
        })
        assert invalid_time.status_code == 302
        with app.app_context():
            assert ScheduleEntry.query.count() == 2
        client.get("/logout")
        teacher_login = client.post("/login", data={"username": "enseignant.test", "password": "Lyttib"})
        assert teacher_login.status_code == 302
        official_teacher = client.get("/enseignant/emploi-du-temps/officiel")
        assert official_teacher.status_code == 200
        assert "Électrotechnique".encode() in official_teacher.data
    print("SCHEDULE_CONFLICT_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
