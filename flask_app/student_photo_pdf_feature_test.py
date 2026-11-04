from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from PIL import Image

from app import app
from pdf_utils import pdf_image_data_uri, render_pdf, student_photo_pdf_path


def make_photo(path, color):
    Image.new("RGB", (480, 640), color).save(path, format="PNG")


def run():
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        first = tmp / "student-one.png"
        second = tmp / "student-two.png"
        make_photo(first, (25, 90, 160))
        make_photo(second, (180, 50, 45))

        # Student.photo sous forme de chemin local, données binaires et fichier.
        path_one = student_photo_pdf_path(str(first), lightweight=True)
        path_two = student_photo_pdf_path(second.read_bytes(), lightweight=True)
        with second.open("rb") as uploaded:
            path_two_file = student_photo_pdf_path(uploaded, lightweight=True)
        assert path_one and path_two and path_two_file
        assert path_one != path_two
        assert Image.open(path_one).size == (255, 340)
        assert Image.open(path_two).size == (255, 340)
        assert student_photo_pdf_path(None) is None
        assert student_photo_pdf_path("") is None
        assert student_photo_pdf_path(str(tmp / "missing.jpg")) is None

        # Le même template groupé reçoit une photo distincte pour chaque élève.
        rows = []
        school_class = SimpleNamespace(
            department=SimpleNamespace(section=SimpleNamespace(name="SECTION TEST")),
            name="CLASSE TEST",
            students=[],
            homeroom_teacher=None,
        )
        empty_data = {
            "categories": [], "overall_points": 0, "class_avg": None,
            "overall_coef": 0, "highest_avg": None, "overall_avg": None,
            "lowest_avg": None, "rank": None, "class_size": 3,
            "nb_above_10": 0, "term_seq_a": 1, "term_seq_b": 2,
            "overall_eval_a_avg": None, "overall_eval_b_avg": None,
            "success_rate": None, "work_marks": SimpleNamespace(
                tableau_honneur=False, travail_insuffisant=False,
                encouragements=False, bon_travail=False,
                felicitations=False, travail_passable=False,
                assez_bon_travail=False,
            ),
            "absences_justified_hours": 0, "absences_non_justified_hours": 0,
            "absences_justified_days": 0, "absences_non_justified_days": 0,
            "conduct_exclusion_label": "", "exclusions": [],
            "avert_conduite": False, "blame_conduite": False,
            "work_appreciation": "",
        }
        for index, (name, path, available) in enumerate(
            (("ÉLÈVE PHOTO", path_one, True), ("ÉLÈVE SANS PHOTO", "", False), ("DEUXIÈME PHOTO", path_two, True))
        ):
            rows.append({
                "student": SimpleNamespace(full_name=name, school_class=school_class),
                "data": dict(empty_data),
                "photo_path": pdf_image_data_uri(path),
                "photo_available": available,
                "bulletin_ref": str(index),
            })

        with app.test_request_context("/test/student-photo-pdf"):
            pdf = render_pdf(
                "pdf/class_bulletins_pdf.html",
                students_data=rows,
                term="Trimestre 1",
                term_ordinal="PREMIER",
                TERM_SEQ_A=1,
                TERM_SEQ_B=2,
                school_year="2026-2027",
            )
        assert pdf is not None
        pdf_bytes = pdf.getvalue()
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1000
        template = Path(app.root_path) / "templates/pdf/_bulletin_body.html"
        assert "Photo non disponible" in template.read_text(encoding="utf-8")

    print("STUDENT_PHOTO_PDF_FEATURE_TEST_OK")


if __name__ == "__main__":
    run()
