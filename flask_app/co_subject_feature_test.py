from datetime import date

from app import app, db
from models import User, Section, Department, SchoolClass, Subject, Teacher, Student, Parent, Course, Grade, ScheduleEntry
from seed import ensure_co_subjects
from utils import bulletin_data, general_average
from pdf_utils import render_pdf


def set_session(client, user):
    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["role"] = user.role
        session["name"] = user.full_name
        session["session_token"] = user.session_token


with app.app_context():
    db.drop_all()
    db.create_all()
    section = Section(name="Section CO", code="CO")
    department = Department(name="Filière CO", code="FCO", section=section)
    director = User(username="proviseur.co", full_name="Proviseur CO", role="directeur", active=True)
    teacher_user = User(username="enseignant.co", full_name="Enseignant CO", role="enseignant", active=True)
    student_user = User(username="eleve.co", full_name="Élève CO", role="eleve", active=True)
    parent_user = User(username="parent.co", full_name="Parent CO", role="parent", active=True)
    censeur_user = User(username="censeur.co", full_name="Censeur CO", role="censeur", section=section, active=True)
    conseiller_user = User(username="conseiller.co", full_name="Conseiller CO", role="conseiller_orientation", active=True)
    director.set_password("Test#2026")
    teacher_user.set_password("Test#2026")
    student_user.set_password("Test#2026")
    parent_user.set_password("Test#2026")
    censeur_user.set_password("Test#2026")
    conseiller_user.set_password("Test#2026")
    teacher = Teacher(user=teacher_user, department=department)
    first_class = SchoolClass(name="Classe CO A", level="1A", department=department)
    second_class = SchoolClass(name="Classe CO B", level="2A", department=department)
    normal_subject = Subject(name="Mathématiques", coefficient=2, category="Enseignements Généraux", department=department)
    parent = Parent(user=parent_user)
    db.session.add_all([section, department, director, teacher_user, student_user, parent_user,
                        censeur_user, conseiller_user, teacher, first_class, second_class,
                        normal_subject, parent])
    db.session.flush()
    student = Student(user=student_user, class_id=first_class.id, matricule="CO-001", first_name="Élève", last_name="CO")
    db.session.add(student)
    parent.children.append(student)
    db.session.commit()

    assert ensure_co_subjects() == 2
    co_subjects = Subject.query.filter_by(name="CO").all()
    assert {subject.class_id for subject in co_subjects} == {first_class.id, second_class.id}
    assert all(subject.timetable_only and subject.coefficient is None and subject.category is None for subject in co_subjects)

    normal_course = Course(subject_id=normal_subject.id, teacher_id=teacher.id, class_id=first_class.id)
    co_course = Course(subject_id=co_subjects[0].id, teacher_id=teacher.id, class_id=first_class.id)
    db.session.add_all([normal_course, co_course])
    db.session.flush()
    db.session.add_all([
        Grade(value=12, max_value=20, type="Évaluation", sequence=1, term="Trimestre 1", date=date.today(), student_id=student.id, course_id=normal_course.id),
        Grade(value=20, max_value=20, type="Évaluation", sequence=1, term="Trimestre 1", date=date.today(), student_id=student.id, course_id=co_course.id),
        ScheduleEntry(course_id=co_course.id, day="Lundi", start_time="07:30", end_time="08:20", published=True),
    ])
    db.session.commit()

    bulletin = bulletin_data(student, "Trimestre 1")
    bulletin_subject_names = {row["course"].subject.name for category in bulletin["categories"] for row in category["rows"]}
    assert "CO" not in bulletin_subject_names
    assert general_average(student.id, "Trimestre 1") == 12.0

    with app.test_client() as client:
        login = client.post("/login", data={"username": "enseignant.co", "password": "Test#2026"})
        assert login.status_code in (302, 303)
        courses_page = client.get("/enseignant/mes-classes")
        assert courses_page.status_code == 200 and b">CO</h3>" not in courses_page.data
        assert client.get(f"/enseignant/notes/{co_course.id}").status_code == 403
        assert client.get(f"/enseignant/appel/{co_course.id}").status_code == 403
        assert client.get("/logout").status_code in (302, 303)
        assert client.post("/login", data={"username": "eleve.co", "password": "Test#2026"}).status_code in (302, 303)
        student_notes = client.get("/eleve/notes")
        assert student_notes.status_code == 200 and b">CO</h3>" not in student_notes.data
        student_schedule = client.get("/eleve/emploi-du-temps")
        assert student_schedule.status_code == 200 and b"CO" in student_schedule.data
        client.get("/logout")
        assert client.post("/login", data={"username": "parent.co", "password": "Test#2026"}).status_code in (302, 303)
        parent_notes = client.get(f"/parent/enfant/{student.id}")
        assert parent_notes.status_code == 200 and b">CO</h3>" not in parent_notes.data
        parent_schedule = client.get(f"/parent/enfant/{student.id}/emploi-du-temps")
        assert parent_schedule.status_code == 200 and b"CO" in parent_schedule.data
        client.get("/logout")
        assert client.post("/login", data={"username": "proviseur.co", "password": "Test#2026"}).status_code in (302, 303)
        class_schedule = client.get(f"/censeur/emplois-du-temps?class_id={first_class.id}")
        assert class_schedule.status_code == 200 and b"CO" in class_schedule.data
        new_class_response = client.post("/directeur/structure/classe/nouvelle", data={
            "department_id": str(department.id), "level": "Tle", "specialty": "NCO",
            "code": "NCO-TLE", "capacity": "48",
        })
        assert new_class_response.status_code in (302, 303)
        new_class = SchoolClass.query.filter_by(code="NCO-TLE").one()
        new_co = Subject.query.filter_by(class_id=new_class.id, name="CO").one()
        assert new_co.timetable_only and new_co.coefficient is None and new_co.category is None
        client.get("/logout")
        assert client.post("/login", data={"username": "censeur.co", "password": "Test#2026"}).status_code in (302, 303)
        schedule_post = client.post(f"/censeur/emplois-du-temps?class_id={first_class.id}", data={
            "subject_id": str(co_subjects[0].id), "teacher_id": str(teacher.id),
            "day": "Mardi", "start_time": "08:20", "end_time": "09:10",
        })
        assert schedule_post.status_code in (302, 303)
        assert ScheduleEntry.query.join(Course).filter(Course.subject_id == co_subjects[0].id,
                                                        ScheduleEntry.day == "Mardi").count() == 1
        censeur_schedule = client.get(f"/censeur/emplois-du-temps?class_id={first_class.id}")
        assert censeur_schedule.status_code == 200 and b"CO" in censeur_schedule.data
        assert client.get("/logout").status_code in (302, 303)
        assert client.post("/login", data={"username": "conseiller.co", "password": "Test#2026"}).status_code in (302, 303)
        counselor_schedule = client.get(f"/censeur/emplois-du-temps?class_id={first_class.id}")
        assert counselor_schedule.status_code == 200 and b"CO" in counselor_schedule.data
        assert client.post(f"/censeur/emplois-du-temps?class_id={first_class.id}", data={"subject_id": str(co_subjects[0].id)}).status_code == 403
        with app.test_request_context("/"):
            bulletin_pdf = render_pdf("pdf/bulletin_pdf.html", student=student, data=bulletin,
                                      term="Trimestre 1", school_year="2025-2026")
        assert bulletin_pdf and bulletin_pdf.getvalue().startswith(b"%PDF")
        assert b"CO" not in bulletin_pdf.getvalue()

    print("CO_SUBJECT_FEATURE_TEST_OK")
