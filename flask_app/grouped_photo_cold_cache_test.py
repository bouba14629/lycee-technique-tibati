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
from reportlab.pdfbase import pdfmetrics


TEST_FULL_NAMES = [
    "Eleve 1 Test",
    "Eleve 2 Test",
    "Eleve 3 Test",
    "Eleve 4 Test",
    "Eleve 5 Test Avec Un Nom Tres Long Qui Force Un Retour",
]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def image_bytes(color, mode="RGB", fmt="PNG"):
    output = io.BytesIO()
    Image.new(mode, (800, 900), color).save(output, format=fmt)
    return output.getvalue()


def assert_photo_dimensions(page, annual=False):
    operations = page.get_contents().operations
    found = 0
    for index, (operands, operator) in enumerate(operations):
        if operator != b"Do":
            continue
        image = page["/Resources"]["/XObject"][operands[0]]
        if not (100 <= image.get("/Width", 0) <= 320 and 100 <= image.get("/Height", 0) <= 400 and image.get("/Height", 0) > image.get("/Width", 0)):
            continue
        matrix, previous_operator = operations[index - 1]
        assert previous_operator == b"cm"
        # xhtml2pdf lit les attributs width/height en pixels (0,75 pt/px).
        # L'image passe de 50x61 à 60x73, soit environ +20 % par côté.
        # Selon la version de xhtml2pdf, la largeur est émise à 28 pt ou
        # 45 pt ; dans les deux cas la hauteur et le format portrait restent
        # ceux du cadre prévu.
        expected_widths = (49.5,) if annual else (28, 45)
        assert min(abs(float(matrix[0]) - expected) for expected in expected_widths) < 0.01, matrix
        assert abs(float(matrix[3]) - (55.5 if annual else 54.75)) < 0.01, matrix
        if annual:
            assert min(abs(float(matrix[4]) - x) for x in (514.25, 528.75)) < .01, matrix
            assert min(abs(float(matrix[5]) - (float(page.mediabox.height) - offset)) for offset in (207.5, 210.51, 211.5)) < .01, matrix
        found += 1
    return found


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalise_text(value):
    return " ".join(str(value or "").split()).casefold()


def _font_text_width(text, font_dict, font_size):
    """Calcule une largeur PDF sans supposer que la police Inter est installée."""
    if not text:
        return 0.0
    size = _as_float(font_size)
    widths = font_dict.get("/Widths") if font_dict else None
    first_char = _as_float(font_dict.get("/FirstChar")) if font_dict else 0
    if widths:
        measured = 0.0
        complete = True
        for char in text:
            code = ord(char)
            index = int(code - first_char)
            if index < 0 or index >= len(widths):
                complete = False
                break
            measured += _as_float(widths[index]) / 1000.0
        if complete:
            return measured * size
    # For Type1 fallback fonts, use the declared BaseFont (the captions are
    # Helvetica-Bold here).  This matters for long captions: regular Helvetica
    # is a few points narrower and would report a false centering failure.
    try:
        base_font = str(font_dict.get("/BaseFont", "Helvetica")) if font_dict else "Helvetica"
        base_font = base_font.rsplit("/", 1)[-1]
        if base_font not in pdfmetrics.getRegisteredFontNames():
            base_font = "Helvetica-Bold" if "Bold" in base_font else "Helvetica"
        return pdfmetrics.stringWidth(text, base_font, size)
    except Exception:
        return len(text) * size * 0.5


def _text_events(page):
    events = []

    def visitor_text(text, cm, tm, font_dict, font_size):
        value = str(text or "")
        stripped = value.strip()
        if not stripped:
            return
        x = _as_float(tm[4]) if tm and len(tm) > 5 else 0.0
        y = _as_float(tm[5]) if tm and len(tm) > 5 else 0.0
        width = _font_text_width(stripped, font_dict, font_size)
        events.append({
            "text": stripped,
            "x0": x,
            "x1": x + width,
            "y": y,
            "font_size": _as_float(font_size),
            "cm": tuple(_as_float(value) for value in (cm or (1, 0, 0, 1, 0, 0))),
            "tm": tuple(_as_float(value) for value in (tm or (1, 0, 0, 1, 0, 0))),
        })

    page.extract_text(visitor_text=visitor_text)
    return events


def _photo_boxes(page):
    """Retourne les matrices cm des images photo, pas celles du logo."""
    operations = page.get_contents().operations
    xobjects = page["/Resources"]["/XObject"]
    boxes = []
    for index, (operands, operator) in enumerate(operations):
        if operator != b"Do":
            continue
        image = xobjects[operands[0]]
        width = _as_float(image.get("/Width"))
        height = _as_float(image.get("/Height"))
        if not (100 <= width <= 320 and 100 <= height <= 400 and height > width):
            continue
        matrix = None
        if index and operations[index - 1][1] == b"cm":
            matrix = operations[index - 1][0]
        if matrix is None:
            continue
        anchor = None
        for previous_operands, previous_operator in reversed(operations[:index - 1]):
            if previous_operator != b"cm" or len(previous_operands) != 6:
                continue
            if (_as_float(previous_operands[0]), _as_float(previous_operands[1]),
                    _as_float(previous_operands[2]), _as_float(previous_operands[3])) != (1.0, 0.0, 0.0, 1.0):
                continue
            if abs(_as_float(previous_operands[4])) > 100:
                anchor = previous_operands
                break
        boxes.append({
            "x0": _as_float(matrix[4]),
            "y0": _as_float(matrix[5]),
            "x1": _as_float(matrix[4]) + abs(_as_float(matrix[0])),
            "y1": _as_float(matrix[5]) + abs(_as_float(matrix[3])),
            "operation_index": index,
            "anchor_x": _as_float(anchor[4]) if anchor is not None else 0.0,
            "anchor_y": _as_float(anchor[5]) if anchor is not None else 0.0,
        })
    return boxes


def _caption_lines(page, full_name, photo_box):
    """Regroupe les fragments tiny du caption, y compris un nom revenu à la ligne."""
    photo_cx = (photo_box["x0"] + photo_box["x1"]) / 2
    name_tokens = _normalise_text(full_name).split()
    events = [
        event for event in _text_events(page)
        if 4.0 <= event["font_size"] <= 6.25
        and abs((event["x0"] + event["x1"]) / 2 - photo_cx) <= 70
        # xhtml2pdf emits the caption and the photo in separate local frames;
        # their surrounding translations identify the same title-cell block.
        and abs(event["cm"][4] - photo_box["anchor_x"]) <= 25
    ]
    lines = []
    for event in sorted(events, key=lambda item: (-item["y"], item["x0"])):
        line = next((line for line in lines if abs(line["y"] - event["y"]) <= 1.5), None)
        if line is None:
            line = {"y": event["y"], "events": []}
            lines.append(line)
        line["events"].append(event)
    for line in lines:
        line["events"].sort(key=lambda item: item["x0"])
        line["text"] = _normalise_text(" ".join(item["text"] for item in line["events"]))
        line["x0"] = min(item["x0"] for item in line["events"])
        line["x1"] = max(item["x1"] for item in line["events"])
        size = max(item["font_size"] for item in line["events"])
        line["y0"] = line["y"] - size * 0.25
        line["y1"] = line["y"] + size * 0.8
        line["cm"] = line["events"][0]["cm"]

    # Prefer the exact caption when pypdf gives it as one visitor fragment.
    exact = [line for line in lines if line["text"] == _normalise_text(full_name)]
    if exact:
        return exact

    # For a wrapped caption, start at the line containing the Eleve N prefix and
    # retain adjacent tiny lines that carry the remaining name tokens.
    prefix = " ".join(name_tokens[:2])
    seeds = [line for line in lines if prefix in line["text"]]
    if not seeds:
        seeds = [line for line in lines if any(token in line["text"] for token in name_tokens)]
    if not seeds:
        return []
    seed = max(seeds, key=lambda line: sum(token in line["text"] for token in name_tokens))
    selected = [line for line in lines if abs(line["cm"][5] - seed["cm"][5]) <= 8]
    return sorted(selected, key=lambda line: -line["y"])


def assert_name_photo_geometry(page, full_name):
    boxes = _photo_boxes(page)
    assert len(boxes) == 1, (full_name, boxes)
    photo = boxes[0]
    lines = _caption_lines(page, full_name, photo)
    assert lines, (full_name, _text_events(page))
    photo_cx = (photo["x0"] + photo["x1"]) / 2
    caption_text = _normalise_text(" ".join(line["text"] for line in lines))
    assert _normalise_text(full_name) in caption_text, (full_name, lines)
    name_events = [
        event for line in lines for event in line.get("events", [])
        if _normalise_text(full_name) in _normalise_text(event.get("text", ""))
    ]
    block_x0 = min((event["x0"] for event in name_events), default=min(line["x0"] for line in lines))
    block_x1 = max((event["x1"] for event in name_events), default=max(line["x1"] for line in lines))
    block_cx = (block_x0 + block_x1) / 2
    # Le modèle trimestriel décale volontairement l’identité et la photo de
    # quelques points vers la droite ; elles doivent rester dans le même bloc.
    assert abs(photo_cx - block_cx) <= 12.0, (full_name, photo, lines)

    # The two templates use different local coordinate origins.  Their common
    # invariant is the PDF matrix translation: the caption's title-cell frame
    # is above the image frame, which verifies “nom puis photo” without relying
    # on xhtml2pdf's varying Tj/TJ operand encoding.
    caption_frame_y = max(line["cm"][5] for line in lines)
    assert caption_frame_y >= photo["anchor_y"] + 2.0, (full_name, photo, lines)


def assert_photos(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == len(TEST_FULL_NAMES), len(reader.pages)
    expected = [(220, 20, 20), (20, 20, 220), None, None, (20, 220, 20)]
    for index, (page, color, full_name) in enumerate(zip(reader.pages, expected, TEST_FULL_NAMES)):
        text = page.extract_text()
        assert f"PHOTO-{index + 1}" in text, (index, text)
        # Le QR ajouté au coin inférieur gauche est carré ; ne le confondons
        # pas avec la photo portrait de l'élève.
        images = [item for item in page.images if 100 <= item.image.width <= 320 and 100 <= item.image.height <= 400 and item.image.height > item.image.width]
        if color is None:
            assert not images, (index, "another student's image was reused")
            assert "Photo non disponible" in " ".join(text.split()), (index, text)
        else:
            assert len(images) == 1, (index, len(images))
            annual = 'BULLETIN ANNUEL' in text
            assert assert_photo_dimensions(page, annual=annual) == 1
            if not annual:
                assert_name_photo_geometry(page, full_name)
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
                last_name = "Test" if index < 4 else TEST_FULL_NAMES[index].split(" ", 2)[2]
                student = Student(matricule=f"PHOTO-{index + 1}", first_name=f"Eleve {index + 1}", last_name=last_name, class_id=school_class.id, photo=photo)
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
                    expected_attributes = ('width="66" height="74"' if 'annual' in template else 'width="60" height="73"')
                    assert expected_attributes in individual_html
                    expected_style = ('width:49.5pt; height:55.5pt;' if 'annual' in template
                                      else 'width:60pt; height:73pt;')
                    assert expected_style in individual_html
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
