import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import (Course, Department, Equipment, Notification, Reservation, Room, ScheduleEntry,
                    SchoolClass, Section, Subject, Teacher, User, db)


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
        school_class = SchoolClass(name="2nde GEL", level="2nde", department=department)
        subject = Subject(name="Électrotechnique", coefficient=2, department=department)
        teacher = Teacher(user=teacher_user, department=department, specialty="Électrotechnique")
        room = Room(name="Atelier GEL", type="Atelier", capacity=30, department=department)
        db.session.add_all([department, school_class, subject, teacher, room])
        db.session.flush()
        course = Course(subject=subject, teacher=teacher, school_class=school_class)
        db.session.add(course)
        db.session.flush()
        db.session.add(ScheduleEntry(course=course, room=room, day="Lundi", start_time="08:00", end_time="10:00", published=True))
        db.session.add(Reservation(room=room, purpose="Réunion pédagogique", date=date(2026, 1, 5),
                                   start_time="10:30", end_time="11:30", requested_by=principal))
        db.session.commit()
        ids = (room.id, school_class.id)

    room_id, class_id = ids
    with app.test_client() as client:
        login = client.post("/login", data={"username": "proviseur.test", "password": "Lyttib"})
        assert login.status_code == 302
        calendar = client.get("/salles/occupation?semaine=2026-01-05")
        assert calendar.status_code == 200
        assert b"Atelier GEL" in calendar.data
        assert b"R\xc3\xa9union p\xc3\xa9dagogique" in calendar.data
        assert b"2nde GEL" in calendar.data
        assert "Taux d’occupation des salles".encode() in calendar.data
        new_equipment = client.post(f"/salles/{room_id}/equipement", data={
            "name": "Vidéoprojecteur", "quantity": "1", "status": "En panne",
        })
        assert new_equipment.status_code == 302
        with app.app_context():
            assert Equipment.query.filter_by(name="Vidéoprojecteur").one().status == "En panne"
            assert Notification.query.filter(Notification.text.contains("Maintenance équipement")).count() == 1
        recurrent = client.post("/salles/reservation", data={
            "room_id": str(room_id), "purpose": "Réunion mensuelle", "date": "2026-01-05",
            "start_time": "12:00", "end_time": "13:00", "repeat_weeks": "3",
        })
        assert recurrent.status_code == 302
        with app.app_context():
            assert Reservation.query.filter_by(purpose="Réunion mensuelle").count() == 3
        conflict = client.post("/salles/reservation", data={
            "room_id": str(room_id), "purpose": "Créneau impossible", "date": "2026-01-12",
            "start_time": "12:30", "end_time": "13:30", "repeat_weeks": "1",
        }, follow_redirects=True)
        assert conflict.status_code == 200
        assert b"R\xc3\xa9servation non cr\xc3\xa9\xc3\xa9e" in conflict.data
        with app.app_context():
            assert Reservation.query.filter_by(purpose="Créneau impossible").count() == 0
        schedule_page = client.get(f"/censeur/emplois-du-temps?class_id={class_id}")
        assert schedule_page.status_code == 200
        assert b"PDF hebdomadaire" in schedule_page.data
    print("FACILITIES_ENHANCEMENTS_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
