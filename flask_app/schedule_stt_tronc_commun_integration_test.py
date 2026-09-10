import os
import tempfile


def main():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tmp, 'schedule-test.db')}"
        os.environ["LTT_ENV"] = "test"
        from app import app, db
        from models import Course, Department, Room, ScheduleEntry, SchoolClass, Section, Subject, Teacher, User

        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with app.app_context():
            db.create_all()
            section_stt = Section(name="Section STT", code="STT")
            section_ind = Section(name="Section IND", code="IND")
            db.session.add_all([section_stt, section_ind])
            db.session.flush()
            principal = User(username="censeur.test", role="censeur", full_name="Censeur Test", section_id=section_stt.id)
            principal.set_password("Lyttib")
            transversal = User(username="censeur.transversal", role="censeur", full_name="Censeur Transversal")
            transversal.set_password("Lyttib")
            crm = User(username="censeur.crm", role="censeur_crm", full_name="Censeur CRM")
            crm.set_password("Lyttib")
            db.session.add_all([principal, transversal, crm])
            db.session.flush()
            dept_a = Department(name="Gestion A", code="G-A", section_id=section_stt.id)
            dept_b = Department(name="Gestion B", code="G-B", section_id=section_stt.id)
            dept_ind = Department(name="Industrie", code="IND", section_id=section_ind.id)
            db.session.add_all([dept_a, dept_b, dept_ind])
            db.session.flush()
            class_a = SchoolClass(name="2nde STT A", level="2nde", department_id=dept_a.id)
            class_b = SchoolClass(name="2nde STT B", level="2nde", department_id=dept_b.id)
            class_other_level = SchoolClass(name="1ere STT", level="1ere", department_id=dept_b.id)
            class_ind = SchoolClass(name="2nde IND", level="2nde", department_id=dept_ind.id)
            shared_subject = Subject(name="Français commun", coefficient=2, category="Enseignements Généraux", department_id=dept_a.id, class_id=None)
            b_shared_subject = Subject(name="Français commun", coefficient=2, category="Enseignements Généraux", department_id=dept_b.id, class_id=None)
            ind_shared_subject = Subject(name="Français commun", coefficient=2, category="Enseignements Généraux", department_id=dept_ind.id, class_id=None)
            class_subject = Subject(name="Matière de 2nde A", coefficient=1, category="Enseignements Généraux", department_id=dept_a.id, class_id=None)
            missing_subject = Subject(name="Économie locale", coefficient=2, category="Enseignements Généraux", department_id=dept_a.id, class_id=None)
            teacher_user = User(username="enseignant.test", role="enseignant", full_name="Enseignant Test")
            teacher_user.set_password("Lyttib")
            db.session.add_all([class_a, class_b, class_other_level, class_ind, shared_subject, b_shared_subject, ind_shared_subject, class_subject, missing_subject, teacher_user])
            db.session.flush()
            class_subject.class_id = class_a.id
            teacher = Teacher(user_id=teacher_user.id, department_id=dept_a.id, specialty="Français")
            room = Room(name="Salle STT", type="Salle", capacity=40, department_id=dept_a.id)
            db.session.add_all([teacher, room])
            db.session.commit()
            ids = class_a.id, class_b.id, class_other_level.id, class_ind.id, shared_subject.id, class_subject.id, missing_subject.id, teacher.id, room.id

        class_a_id, class_b_id, other_level_id, ind_id, shared_subject_id, class_subject_id, missing_subject_id, teacher_id, room_id = ids
        with app.test_client() as client:
            assert client.post("/login", data={"username": "censeur.test", "password": "Lyttib"}).status_code == 302
            valid = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
                "subject_id": shared_subject_id, "teacher_id": teacher_id, "room_id": room_id,
                "day": "Lundi", "start_time": "08:00", "end_time": "10:00",
                "tronc_commun_class_ids": [str(class_b_id)],
            }, follow_redirects=True)
            assert valid.status_code == 200
            with app.app_context():
                entries = ScheduleEntry.query.order_by(ScheduleEntry.id).all()
                assert len(entries) == 2
                assert len({entry.group_key for entry in entries}) == 1
                assert {entry.course.class_id for entry in entries} == {class_a_id, class_b_id}
                assert Course.query.count() == 2

            conflict = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
                "subject_id": shared_subject_id, "teacher_id": teacher_id, "room_id": room_id,
                "day": "Lundi", "start_time": "09:00", "end_time": "11:00",
                "tronc_commun_class_ids": [str(class_b_id)],
            }, follow_redirects=True)
            assert conflict.status_code == 200
            assert b"Conflit d" in conflict.data
            with app.app_context():
                assert ScheduleEntry.query.count() == 2

            client.get("/logout")
            assert client.post("/login", data={"username": "censeur.transversal", "password": "Lyttib"}).status_code == 302
            cross_section = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
                "subject_id": shared_subject_id, "teacher_id": teacher_id, "room_id": room_id,
                "day": "Mardi", "start_time": "08:00", "end_time": "10:00",
                "tronc_commun_class_ids": [str(ind_id)],
            }, follow_redirects=True)
            assert cross_section.status_code == 200
            assert b"Tronc commun" in cross_section.data
            with app.app_context():
                assert ScheduleEntry.query.count() == 4

            incompatible = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
                "subject_id": missing_subject_id, "teacher_id": teacher_id, "room_id": room_id,
                "day": "Mercredi", "start_time": "08:00", "end_time": "10:00",
                "tronc_commun_class_ids": [str(ind_id)],
            }, follow_redirects=True)
            assert incompatible.status_code == 200
            assert "matière sélectionnée n’est pas compatible".encode("utf-8") in incompatible.data
            with app.app_context():
                assert ScheduleEntry.query.count() == 4

            client.get("/logout")
            assert client.post("/login", data={"username": "censeur.test", "password": "Lyttib"}).status_code == 302
            for invalid_id, expected_status in ((other_level_id, 200), (ind_id, 403)):
                rejected = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
                    "subject_id": shared_subject_id, "teacher_id": teacher_id, "room_id": room_id,
                    "day": "Mardi", "start_time": "08:00", "end_time": "10:00",
                    "tronc_commun_class_ids": [str(invalid_id)],
                }, follow_redirects=True)
                assert rejected.status_code == expected_status
                if expected_status == 200:
                    assert b"tronc commun" in rejected.data

            subject_rejected = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
                "subject_id": class_subject_id, "teacher_id": teacher_id, "room_id": room_id,
                "day": "Mercredi", "start_time": "08:00", "end_time": "10:00",
                "tronc_commun_class_ids": [str(class_b_id)],
            }, follow_redirects=True)
            assert subject_rejected.status_code == 200
            assert "rattachée à une seule classe".encode("utf-8") in subject_rejected.data
            with app.app_context():
                assert ScheduleEntry.query.count() == 4

            client.get("/logout")
            assert client.post("/login", data={"username": "censeur.crm", "password": "Lyttib"}).status_code == 302
            crm_insert = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
                "subject_id": shared_subject_id, "teacher_id": teacher_id, "room_id": room_id,
                "day": "Jeudi", "start_time": "08:00", "end_time": "10:00",
                "tronc_commun_class_ids": [str(class_b_id)],
            }, follow_redirects=True)
            assert crm_insert.status_code == 200
            assert b"Tronc commun" in crm_insert.data
            with app.app_context():
                assert ScheduleEntry.query.count() == 6
                assert len({entry.group_key for entry in ScheduleEntry.query.filter(ScheduleEntry.day == "Jeudi").all()}) == 1

    print("SCHEDULE_STT_TRONC_COMMUN_INTEGRATION_TEST_OK")


if __name__ == "__main__":
    main()
