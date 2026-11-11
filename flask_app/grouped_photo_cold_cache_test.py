"""Régression production : stockage distinct du worker HTTP Flask, cache froid.

Base SQLite temporaire exclusivement ; aucun compte réel n'est modifié.
Exécuter : PYTHONPATH=flask_app python3 flask_app/grouped_photo_cold_cache_test.py
"""
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen

from PIL import Image
from pypdf import PdfReader


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def image_bytes(color, mode="RGB", fmt="PNG"):
    output = io.BytesIO()
    Image.new(mode, (800, 900), color).save(output, format=fmt)
    return output.getvalue()


def assert_photo_dimensions(page):
    operations = page.get_contents().operations
    found = 0
    for index, (operands, operator) in enumerate(operations):
        if operator != b"Do":
            continue
        image = page["/Resources"]["/XObject"][operands[0]]
        if not (100 <= image.get("/Width", 0) <= 320 and 100 <= image.get("/Height", 0) <= 400):
            continue
        matrix, previous_operator = operations[index - 1]
        assert previous_operator == b"cm"
        # xhtml2pdf lit les attributs width/height en pixels (0,75 pt/px).
        # L'image passe de 46x56 à 50x61, soit environ +9 % par côté.
        assert abs(float(matrix[0]) - 37.5) < 0.01, matrix
        assert abs(float(matrix[3]) - 45.75) < 0.01, matrix
        found += 1
    return found


def assert_photos(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 5, len(reader.pages)
    expected = [(220, 20, 20), (20, 20, 220), None, None, (20, 220, 20)]
    for index, (page, color) in enumerate(zip(reader.pages, expected)):
        text = page.extract_text()
        assert f"PHOTO-{index + 1}" in text, (index, text)
        images = [item for item in page.images if 100 <= item.image.width <= 320 and 100 <= item.image.height <= 400]
        if color is None:
            assert not images, (index, "another student's image was reused")
            assert "Photo non disponible" in " ".join(text.split()), (index, text)
        else:
            assert len(images) == 1, (index, len(images))
            assert assert_photo_dimensions(page) == 1
            image = images[0].image.convert("RGB")
            pixel = image.getpixel((image.width // 2, image.height // 2))
            assert all(abs(a - b) <= 8 for a, b in zip(pixel, color)), (index, pixel, color)


def main():
    with tempfile.TemporaryDirectory(prefix="ltt-cold-photo-") as tmp:
        storage_port, flask_port = free_port(), free_port()
        counts = {}
        payloads = {
            "/manus-storage/students/red/portrait.png": image_bytes((220, 20, 20, 255), "RGBA"),
            "/manus-storage/students/blue/portrait.png": image_bytes((20, 20, 220)),
            "/manus-storage/students/corrupt.jpg": b"corrupt-image",
            "/manus-storage/students/green.webp": image_bytes((20, 220, 20), fmt="WEBP"),
        }

        class StorageHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                counts[self.path] = counts.get(self.path, 0) + 1
                data = payloads.get(self.path)
                self.send_response(200 if data else 404)
                self.end_headers()
                self.wfile.write(data or b"missing")

            def log_message(self, *_args):
                pass

        storage = HTTPServer(("127.0.0.1", storage_port), StorageHandler)
        thread = threading.Thread(target=storage.serve_forever, daemon=True)
        thread.start()
        os.environ.update({
            "DATABASE_URL": "sqlite:///" + str(Path(tmp) / "test.sqlite"),
            "LTT_ENV": "production",
            "LTT_INITIAL_ADMIN_PASSWORD": "IsolatedTest#2026",
            "LTT_SECRET_KEY": "isolated-cold-cache-test-only",
            "LTT_STORAGE_BASE_URL": f"http://127.0.0.1:{storage_port}",
            "LTT_PORT": str(flask_port),
            "PORT": str(storage_port),
            "LTT_PDF_CACHE_ROOT": str(Path(tmp) / "pdf-cache"),
        })
        from app import app
        from models import db, User, Section, Department, SchoolClass, Subject, Teacher, Course, ScheduleEntry, Student, Grade
        import pdf_utils

        with app.app_context():
            section = Section(name="Test", code="TCOLD")
            db.session.add(section); db.session.flush()
            department = Department(name="Test", code="TCOLD", section_id=section.id)
            db.session.add(department); db.session.flush()
            school_class = SchoolClass(name="Test photo", level="Tle", department_id=department.id)
            db.session.add(school_class); db.session.flush()
            teacher_user = User(username="isolated.photo.teacher", full_name="Enseignant Test", role="enseignant")
            teacher_user.set_password("Test#2026")
            director = User(username="isolated.photo.director", full_name="Directeur Test", role="directeur")
            director.set_password("Test#2026")
            director.session_token = "isolated-test-session-token"
            db.session.add_all([teacher_user, director]); db.session.flush()
            teacher = Teacher(user_id=teacher_user.id)
            subject = Subject(name="Mathématiques", department_id=department.id, class_id=school_class.id)
            db.session.add_all([teacher, subject]); db.session.flush()
            course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id)
            db.session.add(course); db.session.flush()
            db.session.add(ScheduleEntry(course_id=course.id, day="Lundi", start_time="08:00", end_time="09:00", published=True))
            photos = [list(payloads)[0], list(payloads)[1], None, list(payloads)[2], "https://public.example" + list(payloads)[3]]
            for index, photo in enumerate(photos):
                student = Student(matricule=f"PHOTO-{index + 1}", first_name=f"Eleve {index + 1}", last_name="Test", class_id=school_class.id, photo=photo)
                db.session.add(student); db.session.flush()
                db.session.add(Grade(student_id=student.id, course_id=course.id, value=12, term="Trimestre 1"))
            db.session.commit()
            class_id, user_id = school_class.id, director.id

        serializer = app.session_interface.get_signing_serializer(app)
        cookie = serializer.dumps({"user_id": user_id, "role": "directeur", "session_token": "isolated-test-session-token"})
        process = None
        try:
            log = open(Path(tmp) / "gunicorn.log", "w+")
            process = subprocess.Popen([
                sys.executable, "-m", "gunicorn", "--workers", "1", "--timeout", "30",
                "--bind", f"127.0.0.1:{flask_port}", "wsgi:app",
            ], cwd=str(Path(__file__).parent), env=os.environ.copy(), stdout=log, stderr=log)
            for _ in range(60):
                if process.poll() is not None:
                    log.seek(0); raise AssertionError(log.read())
                try:
                    with urlopen(f"http://127.0.0.1:{flask_port}/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.2)
            else:
                raise AssertionError("test worker did not become ready")

            for term in ("Trimestre+1", "Trimestre+3"):
                start = time.monotonic()
                req = Request(f"http://127.0.0.1:{flask_port}/censeur/bulletins/classe/{class_id}/telecharger.pdf?term={term}", headers={"Cookie": "session=" + cookie})
                with urlopen(req, timeout=25) as response:
                    assert response.status == 200
                    assert response.headers.get_content_type() == "application/pdf", response.url
                    raw = response.read()
                assert_photos(raw)
                print("HTTP_PDF_PHOTOS_OK", term, "seconds", round(time.monotonic() - start, 2), flush=True)
            for path in payloads:
                assert counts[path] == 1, (path, counts)
            print("COLD_CACHE_DISTINCT_PHOTOS_AND_SINGLE_DOWNLOAD_OK", flush=True)

            # Le secours assemble les mêmes sources et ne passe jamais photo_available=False.
            from censeur_routes import censeur_bulletins_class_pdf
            with app.test_request_context(f"/censeur/bulletins/classe/{class_id}/telecharger.pdf?term=Trimestre+1", base_url=f"http://127.0.0.1:{flask_port}"):
                from flask import session
                session.update(user_id=user_id, role="directeur")
                original = pdf_utils.render_pdf
                calls = []

                def fail_grouped_only(template, **context):
                    rows = context.get("students_data", [])
                    calls.append(rows)
                    if len(rows) > 1:
                        return None
                    return original(template, **context)

                with patch.object(pdf_utils, "render_pdf", side_effect=fail_grouped_only):
                    response = censeur_bulletins_class_pdf(class_id)
                    response.direct_passthrough = False
                    assert_photos(response.get_data())
                assert len(calls) == 6, len(calls)
                first = calls[0][0]
                from utils import annual_bulletin_data, get_current_school_year
                from flask import render_template
                for template, data in (
                    ("pdf/bulletin_pdf.html", first["data"]),
                    ("pdf/bulletin_annual_pdf.html", annual_bulletin_data(first["student"])),
                ):
                    individual_html = render_template(template, student=first["student"], data=data,
                                                      student_photo_path=first["photo_path"], photo_available=True,
                                                      school_year=get_current_school_year(), term="Trimestre 1",
                                                      term_ordinal="PREMIER", TERM_SEQ_A=1, TERM_SEQ_B=2)
                    assert 'style="width:50pt; height:61pt;" width="50" height="61"' in individual_html
                    assert first["photo_path"] in individual_html
                print("ENLARGED_PHOTO_DIMENSIONS_GROUPED_AND_INDIVIDUAL_HTML_MATCH_OK", flush=True)
            print("ASSEMBLY_FALLBACK_PRESERVES_PHOTOS_OK", flush=True)
        finally:
            if process:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
            storage.shutdown(); storage.server_close()

    print("GROUPED_PHOTO_COLD_CACHE_TEST_OK", flush=True)


if __name__ == "__main__":
    main()
