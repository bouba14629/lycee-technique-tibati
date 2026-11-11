import io
import json
import os
import sys
import tempfile
from PIL import Image
from werkzeug.datastructures import FileStorage

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-photo-formats.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"
os.environ["JWT_SECRET"] = "formats-test-secret"
os.environ["PORT"] = "3000"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import student_photo_url
import directeur_routes


class FakeUploadResponse:
    def __init__(self, url):
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"url": self.url}).encode("utf-8")


for extension, mime in (("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")):
    expected_url = f"/manus-storage/students/formats-{extension}." + extension
    original_urlopen = directeur_routes.urlopen
    directeur_routes.urlopen = lambda _request, timeout=20, url=expected_url: FakeUploadResponse(url)
    try:
        result = directeur_routes.save_student_photo(
            FileStorage(stream=io.BytesIO(b"image-bytes"), filename=f"portrait.{extension}"),
            f"FORMATS-{extension.upper()}",
        )
    finally:
        directeur_routes.urlopen = original_urlopen
    assert result == expected_url
    assert mime in {"image/jpeg", "image/png", "image/webp"}

from app import app
from pdf_utils import get_student_photo_source

with app.test_request_context():
    assert student_photo_url(None).endswith("avatar_placeholder_0074e93d.png")
    assert student_photo_url("portrait.jpg").endswith("uploads/students/portrait.jpg")
    assert student_photo_url("uploads/students/portrait.png").endswith("uploads/students/portrait.png")
    assert student_photo_url("static/uploads/students/portrait.webp").endswith("uploads/students/portrait.webp")
    assert student_photo_url("/static/uploads/students/portrait.jpeg").endswith("/static/uploads/students/portrait.jpeg")
    assert student_photo_url("/manus-storage/students/portrait.jpg") == "/manus-storage/students/portrait.jpg"

    with tempfile.TemporaryDirectory() as tmpdir:
        photo_path = os.path.join(tmpdir, "student.png")
        Image.new("RGB", (90, 120), (25, 80, 140)).save(photo_path, format="PNG")
        student = type("PhotoStudent", (), {"id": 101, "photo": photo_path})()
        source = get_student_photo_source(student)
        assert source and source.startswith("data:image/jpeg;base64,")
        assert get_student_photo_source(type("PhotoStudent", (), {"id": 102, "photo": None})()) is None
        assert get_student_photo_source(type("PhotoStudent", (), {"id": 103, "photo": os.path.join(tmpdir, "missing.jpg")})()) is None
        corrupt_path = os.path.join(tmpdir, "corrupt.jpg")
        with open(corrupt_path, "wb") as corrupt_file:
            corrupt_file.write(b"not-an-image")
        assert get_student_photo_source(type("PhotoStudent", (), {"id": 104, "photo": corrupt_path})()) is None

print("STUDENT_PHOTO_FORMATS_TEST_OK")
