import os
import sys
import zipfile
from io import BytesIO

from openpyxl import Workbook

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-import-feature.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

sys.path.insert(0, os.path.dirname(__file__))

from app import app
import import_routes
from models import Attendance, Course, Department, SchoolClass, Section, Student, Subject, Teacher, User, db


def login_founder(client):
    initial_password = os.environ["LTT_INITIAL_ADMIN_PASSWORD"]
    login = client.post("/login", data={"username": "proviseur", "password": initial_password})
    assert "/premiere-connexion" in login.headers["Location"]
    changed = client.post("/premiere-connexion", data={
        "password": "NouveauMotDePasse#2026",
        "confirmation": "NouveauMotDePasse#2026",
    })
    assert "/dashboard" in changed.headers["Location"]


def seed_structure():
    section = Section(name="Section test", code="TST")
    db.session.add(section); db.session.flush()
    department = Department(name="Filière test", code="FT", section_id=section.id)
    db.session.add(department); db.session.flush()
    school_class = SchoolClass(name="1A FT", level="1A", department_id=department.id)
    db.session.add(school_class); db.session.commit()
    other_department = Department(name="Filière voisine", code="FV", section_id=section.id)
    db.session.add(other_department); db.session.flush()
    other_class = SchoolClass(name="1A FV", level="1A", department_id=other_department.id)
    db.session.add(other_class); db.session.commit()
    return department, school_class, other_department, other_class


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        department, school_class, other_department, other_class = seed_structure()
        department_id, class_id = department.id, school_class.id
        other_department_id, other_class_id = other_department.id, other_class.id

    with app.test_client() as client:
        login_founder(client)

        teacher_csv = (
            "Nom complet,Email,Téléphone,Département,Spécialité,Grade,Heures dues\n"
            "Alice TCHUENTE,alice@example.cm,699000000,FT,Informatique,Grade local personnalisé,18\n"
        ).encode()
        teacher_response = client.post("/directeur/utilisateurs/import", data={
            "department_id": str(department_id),
            "import_file": (BytesIO(teacher_csv), "enseignants.csv"),
        }, content_type="multipart/form-data")
        assert teacher_response.status_code in (302, 303)

        teacher_split_name_csv = (
            "NOM,Prénom,Email,Téléphone,Département,Spécialité\n"
            "NGO,Natacha,natacha@example.cm,699000001,FT,Automatisme\n"
        ).encode()
        split_name_response = client.post("/directeur/utilisateurs/import", data={
            "import_file": (BytesIO(teacher_split_name_csv), "enseignants_nom_prenom.csv"),
        }, content_type="multipart/form-data")
        assert split_name_response.status_code in (302, 303)

        teacher_workbook = Workbook()
        teacher_sheet = teacher_workbook.active
        teacher_sheet.append(["Noms et prénoms", "Département", "Spécialité"])
        teacher_sheet.append(["MBOG André", "FT", "Électronique"])
        teacher_buffer = BytesIO()
        teacher_workbook.save(teacher_buffer)
        teacher_buffer.seek(0)
        workbook_teacher_response = client.post("/directeur/utilisateurs/import", data={
            "import_file": (teacher_buffer, "enseignants_noms_prenoms.xlsx"),
        }, content_type="multipart/form-data")
        assert workbook_teacher_response.status_code in (302, 303)

        student_csv = (
            "Nom complet,Matricule,Classe,Sexe,Date de naissance,Lieu de naissance,Redoublant\n"
            "Paul MBOG,MAT-001,1A FT,M,2008-09-14,Tibati,Oui\n"
        ).encode()
        student_response = client.post("/eleves/import", data={
            "class_id": str(class_id),
            "department_id": str(department_id),
            "import_file": (BytesIO(student_csv), "eleves.csv"),
        }, content_type="multipart/form-data")
        assert student_response.status_code in (302, 303)

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Nom complet", "Matricule", "Sexe"])
        worksheet.append(["Jeanne MBOG", "MAT-002", "F"])
        workbook_buffer = BytesIO()
        workbook.save(workbook_buffer)
        workbook_buffer.seek(0)
        xlsx_response = client.post("/eleves/import", data={
            "class_id": str(class_id),
            "import_file": (workbook_buffer, "eleves.xlsx"),
        }, content_type="multipart/form-data")
        assert xlsx_response.status_code in (302, 303)

        preview_csv = b"Nom complet,Matricule,Sexe\nMarc PHOTO,MAT-PHOTO,M\n"
        photo_archive = BytesIO()
        with zipfile.ZipFile(photo_archive, "w") as archive:
            archive.writestr("MAT-PHOTO.jpg", b"\xff\xd8\xff\xd9")
        photo_archive.seek(0)
        original_save_photo = import_routes.save_student_photo
        import_routes.save_student_photo = lambda _file, matricule: f"/manus-storage/students/{matricule}.jpg"
        preview_response = client.post("/eleves/import/previsualiser", data={
            "class_id": str(class_id),
            "import_file": (BytesIO(preview_csv), "eleves_avec_photo.csv"),
            "photos_zip": (photo_archive, "photos_eleves.zip"),
        }, content_type="multipart/form-data")
        assert preview_response.status_code == 200
        assert b"V\xc3\xa9rifiez avant d\xe2\x80\x99importer" in preview_response.data
        assert b"Reconnue" in preview_response.data
        mismatched_preview = client.post("/eleves/import/previsualiser", data={
            "department_id": str(department_id), "class_id": str(other_class_id),
            "import_file": (BytesIO(preview_csv), "eleves_filiere_incoherente.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)
        assert mismatched_preview.status_code == 200
        assert b"classe cible ne rel\xc3\xa8ve pas de la fili\xc3\xa8re" in mismatched_preview.data
        confirm_response = client.post("/eleves/import/confirmer")
        import_routes.save_student_photo = original_save_photo
        assert confirm_response.status_code in (302, 303)

        invalid_csv = b"Nom complet,Classe\nEleve SANSCLASSE,INCONNUE\n"
        invalid_response = client.post("/eleves/import", data={
            "import_file": (BytesIO(invalid_csv), "eleves_invalides.csv"),
        }, content_type="multipart/form-data")
        assert invalid_response.status_code in (302, 303)
        invalid_file_response = client.post("/eleves/import", data={
            "import_file": (BytesIO(b"fichier sans format"), "eleves.txt"),
        }, content_type="multipart/form-data", follow_redirects=True)
        assert invalid_file_response.status_code == 200
        assert b"format non pris en charge" in invalid_file_response.data
        corrupt_xlsx_response = client.post("/eleves/import", data={
            "import_file": (BytesIO(b"classeur xlsx corrompu"), "eleves_corrompus.xlsx"),
        }, content_type="multipart/form-data", follow_redirects=True)
        assert corrupt_xlsx_response.status_code == 200
        assert b"fichier XLSX illisible ou corrompu" in corrupt_xlsx_response.data
        report = client.get("/directeur/imports/rapport")
        assert report.status_code == 200
        assert b"Lignes" in report.data
        report_excel = client.get("/directeur/imports/rapport.xlsx")
        assert report_excel.status_code == 200
        assert report_excel.data[:2] == b"PK"
        report_pdf = client.get("/directeur/imports/rapport.pdf")
        assert report_pdf.status_code == 200
        assert report_pdf.data[:4] == b"%PDF"

        template_response = client.get("/directeur/imports/modele/eleves.xlsx")
        assert template_response.status_code == 200
        assert template_response.data[:2] == b"PK"
        users_screen = client.get("/directeur/utilisateurs")
        new_user_screen = client.get("/directeur/utilisateurs/nouveau")
        enrollment_screen = client.get("/eleves/inscription")
        with app.app_context():
            subject = Subject(name="Matière test", coefficient=2, department_id=department_id)
            db.session.add(subject); db.session.flush()
            course = Course(subject_id=subject.id, teacher_id=Teacher.query.filter(Teacher.specialty == "Informatique").one().id, class_id=class_id)
            db.session.add(course); db.session.flush()
            student = Student.query.filter_by(matricule="MAT-001").one()
            for _ in range(3):
                db.session.add(Attendance(student_id=student.id, course_id=course.id, type="Absence"))
            db.session.commit()
        dashboard = client.get("/dashboard")
        assert users_screen.status_code == enrollment_screen.status_code == dashboard.status_code == 200
        assert new_user_screen.status_code == 200
        assert b'Saisie libre' in users_screen.data and b'teacher-grade-suggestions' in new_user_screen.data
        assert b"CSV" in users_screen.data
        assert b"CSV" in enrollment_screen.data
        assert b"Import rapide par classe" in enrollment_screen.data
        assert b'id="import-department"' in enrollment_screen.data
        assert b'id="import-class"' in enrollment_screen.data
        assert f'data-import-class-department-id="{department_id}"'.encode() in enrollment_screen.data
        assert f'data-import-class-department-id="{other_department_id}"'.encode() in enrollment_screen.data
        assert b"filterImportClasses" in enrollment_screen.data
        assert b'name="photo"' in enrollment_screen.data
        assert b'name="photos_zip"' in enrollment_screen.data
        assert b"Pr\xc3\xa9visualiser avant l\xe2\x80\x99import" in enrollment_screen.data
        assert b"\xc3\x89l\xc3\xa8ves inscrits" in dashboard.data
        assert b">3</div><div class=\"kpi-label\">\xc3\x89l\xc3\xa8ves inscrits" in dashboard.data
        assert b">3</div><div class=\"kpi-label\">Enseignants" in dashboard.data
        assert b"Absences" in dashboard.data
        assert b"\xc3\x89valuations" in dashboard.data
        assert b"Alerte critique" in dashboard.data

        with app.app_context():
            teacher_user_id = Teacher.query.filter(Teacher.specialty == "Informatique").one().user_id
        custom_grade_update = client.post(f"/directeur/utilisateurs/{teacher_user_id}/modifier", data={
            "full_name": "Alice TCHUENTE", "email": "alice@example.cm", "phone": "699000000",
            "grade": "Grade saisi librement", "specialty": "Informatique", "hours_due": "18",
        })
        assert custom_grade_update.status_code in (302, 303)

    with app.app_context():
        assert Teacher.query.count() == 3
        assert Teacher.query.filter(Teacher.specialty == "Informatique").one().grade == "Grade saisi librement"
        assert Student.query.count() == 3
        assert User.query.filter_by(role="enseignant").count() == 3
        assert User.query.filter_by(full_name="NGO Natacha", role="enseignant").count() == 1
        assert User.query.filter_by(full_name="MBOG André", role="enseignant").count() == 1
        assert User.query.filter_by(role="eleve").count() == 3
        student = Student.query.filter_by(matricule="MAT-001").one()
        assert student.matricule == "MAT-001"
        assert student.class_id == class_id
        assert student.is_repeater is True
        assert Student.query.filter_by(matricule="MAT-PHOTO").one().photo.endswith("MAT-PHOTO.jpg")
    print("IMPORT_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
