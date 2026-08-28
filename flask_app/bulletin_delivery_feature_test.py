import os
from io import BytesIO

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-bulletin-delivery.sqlite"
os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app
from models import (BulletinApproval, Course, Department, Grade, Notification, Parent, SchoolClass,
                    Section, Student, Subject, Teacher, User, db)


def add_user(username, role):
    user = User(username=username, full_name=username, role=role, active=True)
    user.set_password("Test#2026")
    db.session.add(user)
    db.session.flush()
    return user


with app.app_context():
    db.drop_all()
    db.create_all()
    censeur = add_user("censeur.delivery", "censeur")
    teacher_user = add_user("enseignant.delivery", "enseignant")
    teacher_user.civility = "Mme."
    student_user = add_user("eleve.delivery", "eleve")
    parent_user = add_user("parent.delivery", "parent")
    section = Section(name="Section Delivery", code="DEL")
    db.session.add(section); db.session.flush()
    department = Department(name="Filière Delivery", code="DEL", section_id=section.id)
    db.session.add(department); db.session.flush()
    school_class = SchoolClass(name="Classe Delivery", level="Test", department_id=department.id)
    subject = Subject(name="Mathématiques", coefficient=2, department_id=department.id)
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
    db.session.add_all([school_class, subject, teacher]); db.session.flush()
    school_class.homeroom_teacher_id = teacher.id
    course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id)
    student = Student(user_id=student_user.id, class_id=school_class.id, matricule="DEL-001", first_name="Élève", last_name="Diffusion")
    parent = Parent(user_id=parent_user.id)
    db.session.add_all([course, student, parent]); db.session.flush()
    parent.children.append(student)
    db.session.add(Grade(value=14, student_id=student.id, course_id=course.id, term="Trimestre 1", sequence=1, type="Évaluation"))
    db.session.commit()
    class_id, student_id = school_class.id, student.id

    with app.test_client() as client:
        client.post("/login", data={"username": "eleve.delivery", "password": "Test#2026"})
        waiting = client.get("/eleve/bulletin?term=Trimestre+1")
        assert waiting.status_code == 200 and b"Bulletin en pr" in waiting.data and b"Consulter les notes" in waiting.data
        assert b"window.print" not in waiting.data and b"T\xc3\xa9l\xc3\xa9charger" not in waiting.data
        assert client.get(f"/eleves/{student_id}/bulletin/telecharger?term=Trimestre+1").status_code == 403
        client.post("/login", data={"username": "censeur.delivery", "password": "Test#2026"})
        term_two_list = client.get(f"/censeur/bulletins?class_id={class_id}&term=Trimestre+2")
        assert term_two_list.status_code == 200
        assert b"telecharger.pdf?term=Trimestre+2" in term_two_list.data
        annual_list = client.get(f"/censeur/bulletins?class_id={class_id}&term=Annuel")
        assert annual_list.status_code == 200 and b"Bulletin annuel" in annual_list.data
        assert b"telecharger.pdf?term=Annuel" in annual_list.data
        assert b"Trimestre 3" not in annual_list.data
        quarterly_list = client.get(f"/censeur/bulletins?class_id={class_id}&term=Trimestre+1")
        assert quarterly_list.status_code == 200 and b"Appr\xc3\xa9cier" in quarterly_list.data
        appreciation_update = client.post(f"/censeur/bulletins/{student_id}/appreciation", data={
            "term": "Trimestre 1", "content": "Efforts réguliers attendus pour consolider les acquis.",
        })
        assert appreciation_update.status_code in (302, 303)
        term_two_bulk_pdf = client.get(f"/censeur/bulletins/classe/{class_id}/telecharger.pdf?term=Trimestre+2")
        assert term_two_bulk_pdf.status_code == 200 and term_two_bulk_pdf.data[:4] == b"%PDF"
        assert b"Trimestre_2" in term_two_bulk_pdf.headers["Content-Disposition"].encode()
        annual_bulk_pdf = client.get(f"/censeur/bulletins/classe/{class_id}/telecharger.pdf?term=Annuel")
        assert annual_bulk_pdf.status_code == 200 and annual_bulk_pdf.data[:4] == b"%PDF"
        assert b"Bulletins_annuels" in annual_bulk_pdf.headers["Content-Disposition"].encode()
        with open("/tmp/ltt-bulletins-annuels-groupes.pdf", "wb") as output:
            output.write(annual_bulk_pdf.data)
        preview = client.get(f"/eleves/{student_id}/bulletin?term=Trimestre+1")
        assert preview.status_code == 200 and b"Aper\xc3\xa7u avant impression" in preview.data
        assert preview.data.count(b"SECTION DELIVERY") == 1
        assert b"R\xc3\xa9f. :" not in preview.data
        assert b"SECTION :" not in preview.data
        assert b"Section Section Delivery" not in preview.data
        assert b"Efforts r\xc3\xa9guliers attendus" in preview.data
        assert b"Mme. enseignant.delivery" in preview.data
        assert b"2CE1TEFD110320092" in preview.data
        quarterly_template = open("templates/pdf/_bulletin_body.html", encoding="utf-8").read()
        quarterly_pdf_template = open("templates/pdf/bulletin_pdf.html", encoding="utf-8").read()
        grouped_template = open("templates/pdf/class_bulletins_pdf.html", encoding="utf-8").read()
        annual_pdf_template = open("templates/pdf/bulletin_annual_pdf.html", encoding="utf-8").read()
        preview_template = open("templates/bulletin.html", encoding="utf-8").read()
        assert "profile-table profile-block" in quarterly_template and "term-average" in quarterly_template and "colspan=\"4\"" in quarterly_template
        assert "Moyenne trimestrielle" in quarterly_template and "Notes trimestrielles" in quarterly_template
        assert 'width="8%">Notes trimestrielles' in quarterly_template and 'width="36%">Appréciations/Signatures' in quarterly_template
        assert 'width:34%">Appréciations/Signatures' in annual_pdf_template
        assert quarterly_template.count('font-size:6.3pt;">Mle : 2CE1TEFD110320092') == 2 and 'width="64"' in quarterly_template
        assert 'padding-left:10pt;' in quarterly_template and 'meta-table td:last-child { padding-left:10pt; }' in quarterly_pdf_template
        assert preview_template.count('font-size:9.5px;">Mle : 2CE1TEFD110320092') == 2 and 'width="68"' in preview_template
        assert 'width="52"' in annual_pdf_template and '.meta td:last-child { padding-left:10pt; }' in annual_pdf_template
        assert quarterly_template.index("Coefficient</td>") < quarterly_template.index("Moyenne du premier</td>")
        assert "font-weight: bold" in quarterly_pdf_template
        assert "Excellent trimestre, continuez ainsi." not in quarterly_template
        assert "student_photo_path=row.photo_path" in grouped_template
        assert "row.course.teacher.user.formal_name" in quarterly_template
        assert "homeroom_teacher.user.formal_name" in quarterly_template
        assert "row.teacher.user.formal_name" in annual_pdf_template
        assert "row.teacher.user.formal_name" in open("templates/pdf/class_annual_bulletins_pdf.html", encoding="utf-8").read()
        annual_generation = client.get(f"/censeur/bulletins/classe/{class_id}/annuels/generer")
        assert annual_generation.status_code == 200 and b"G\xc3\xa9n\xc3\xa9ration des bulletins annuels" in annual_generation.data
        assert b"PDF annuel" in annual_generation.data and b"Aper\xc3\xa7u" in annual_generation.data
        annual_preview = client.get(f"/censeur/bulletins/annuel/{student_id}")
        assert annual_preview.status_code == 200
        assert b"Pr\xc3\xa9visualisation avant impression" in annual_preview.data
        assert b"preview=1" in annual_preview.data
        annual_inline_pdf = client.get(f"/censeur/bulletins/annuel/{student_id}.pdf?preview=1")
        assert annual_inline_pdf.status_code == 200 and annual_inline_pdf.data[:4] == b"%PDF"
        annual_pdf = client.get(f"/censeur/bulletins/annuel/{student_id}.pdf")
        assert annual_pdf.status_code == 200 and annual_pdf.data[:4] == b"%PDF"
        with open("/tmp/ltt-bulletin-annual-section.pdf", "wb") as output:
            output.write(annual_pdf.data)
        validation = client.post(f"/censeur/bulletins/classe/{class_id}/valider", data={"term": "Trimestre 1", "official_release_date": "2026-08-18"})
        assert validation.status_code in (302, 303)
        assert BulletinApproval.query.filter_by(class_id=class_id, term="Trimestre 1").one()
        validated_pdf = client.get(f"/eleves/{student_id}/bulletin/telecharger?term=Trimestre+1")
        assert validated_pdf.status_code == 200 and validated_pdf.data[:4] == b"%PDF"
        with open("/tmp/ltt-bulletin-quarterly-section.pdf", "wb") as output:
            output.write(validated_pdf.data)
        revoked = client.post(f"/censeur/bulletins/classe/{class_id}/annuler-validation", data={"term": "Trimestre 1", "reason": "Correction de note"})
        assert revoked.status_code in (302, 303)
        assert BulletinApproval.query.filter_by(class_id=class_id, term="Trimestre 1", status="Retiré").one().revocation_reason == "Correction de note"
        client.post("/login", data={"username": "eleve.delivery", "password": "Test#2026"})
        waiting_again = client.get("/eleve/bulletin?term=Trimestre+1")
        assert waiting_again.status_code == 200 and b"Bulletin en pr" in waiting_again.data
        client.post("/login", data={"username": "censeur.delivery", "password": "Test#2026"})
        client.post(f"/censeur/bulletins/classe/{class_id}/valider", data={"term": "Trimestre 1", "official_release_date": "2026-08-18"})
        students_pdf = client.get(f"/eleves/export.pdf?class_id={class_id}")
        assert students_pdf.status_code == 200 and students_pdf.data[:4] == b"%PDF"
        client.post("/login", data={"username": "eleve.delivery", "password": "Test#2026"})
        private_bulletin = client.get("/eleve/bulletin?term=Trimestre+1")
        assert private_bulletin.status_code == 200 and b"Bulletin priv" in private_bulletin.data
        notes = client.get("/eleve/notes?term=Trimestre+1")
        assert notes.status_code == 200 and b"Math" in notes.data
        assert Notification.query.filter_by(user_id=student_user.id).count() == 1
        client.post("/login", data={"username": "parent.delivery", "password": "Test#2026"})
        parent_notes = client.get(f"/parent/enfant/{student_id}?term=Trimestre+1")
        assert parent_notes.status_code == 200 and b"Math" in parent_notes.data
        assert b"window.print" not in parent_notes.data
        assert client.get(f"/eleves/{student_id}/bulletin/telecharger.xlsx?term=Trimestre+1").status_code == 403
        assert Notification.query.filter_by(user_id=parent_user.id).count() == 1

print("BULLETIN_DELIVERY_FEATURE_TEST_OK")
