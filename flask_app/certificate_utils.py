"""Génération des certificats de scolarité à partir du modèle officiel importé."""
from __future__ import annotations

import re
import subprocess
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "documents" / "CERTIFICATDESCOLARITE.docx"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
ET.register_namespace("w", W_NS)


def _replace_paragraph_text(root, predicate, replacement: str) -> bool:
    """Remplace le texte d’un paragraphe en conservant sa mise en page Word."""
    for paragraph in root.findall(".//w:p", NS):
        text_nodes = paragraph.findall(".//w:t", NS)
        current = "".join(node.text or "" for node in text_nodes)
        if not predicate(current):
            continue
        if not text_nodes:
            return False
        text_nodes[0].text = replacement
        for node in text_nodes[1:]:
            node.text = ""
        return True
    return False


def _date_text(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "________________"


def _parents_text(student) -> tuple[str, str]:
    parents = list(getattr(student, "parents", []) or [])
    names = [getattr(getattr(parent, "user", None), "full_name", "") for parent in parents]
    names = [name.strip() for name in names if name and name.strip()]
    return (names + ["________________", "________________"])[:2]


def _render_docx(student, school_year: str, principal_name: str, certificate_number: str = "") -> bytes:
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"Modèle absent : {TEMPLATE_PATH}")
    year_start, _, year_end = (school_year or "").partition("-")
    year_label = f"{year_start}/{year_end}" if year_start and year_end else school_year or "202___/202__"
    father_or_mother, second_parent = _parents_text(student)
    class_name = getattr(getattr(student, "school_class", None), "name", None) or "________________"
    first_name = (getattr(student, "first_name", "") or "").strip()
    last_name = (getattr(student, "last_name", "") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part) or "________________"
    principal = (principal_name or "").strip() or "_____________________________"
    reference = certificate_number.strip() or "______"
    replacements = [
        (lambda text: text.startswith("N°") and "/CS/" in text,
         f"N°{reference}/CS/H48.02/LT-TIB."),
        (lambda text: text.startswith("Je soussigné"),
         f"Je soussigné, {principal}, Proviseur du Lycée Technique de Tibati"),
        (lambda text: text.startswith("Certifie que l’élève"),
         f"Certifie que l’élève : {full_name}"),
        (lambda text: text.startswith("Matricule"),
         f"Matricule : {getattr(student, 'matricule', '') or '________________'}"),
        (lambda text: text.startswith("Né (e) le"),
         f"Né (e) le {_date_text(getattr(student, 'dob', None))} à {getattr(student, 'birth_place', None) or '________________'}"),
        (lambda text: text.startswith("Fils (Fille) de"),
         f"Fils (Fille) de {father_or_mother} et de {second_parent}"),
        (lambda text: text.startswith("Est (a été)"),
         f"Est (a été) régulièrement élève dans mon établissement scolaire en classe de {class_name}"),
        (lambda text: text.startswith("Année scolaire"), f"Année scolaire {year_label}"),
        (lambda text: text.startswith("Tibati, le"), f"Tibati, le {date.today().strftime('%d/%m/%Y')}"),
    ]
    with ZipFile(TEMPLATE_PATH, "r") as source:
        document_xml = source.read("word/document.xml")
        root = ET.fromstring(document_xml)
        for predicate, replacement in replacements:
            _replace_paragraph_text(root, predicate, replacement)
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with tempfile.TemporaryDirectory(prefix="ltt-cert-docx-") as workdir:
            docx_path = Path(workdir) / "certificat.docx"
            pdf_dir = Path(workdir) / "pdf"
            pdf_dir.mkdir()
            with ZipFile(docx_path, "w", ZIP_DEFLATED) as target:
                for info in source.infolist():
                    target.writestr(info, updated_xml if info.filename == "word/document.xml" else source.read(info.filename))
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(pdf_dir), str(docx_path)],
                check=False, capture_output=True, text=True, timeout=30,
            )
            pdf_path = pdf_dir / "certificat.pdf"
            if result.returncode != 0 or not pdf_path.is_file():
                raise RuntimeError(f"Conversion du certificat impossible : {result.stderr or result.stdout}")
            return pdf_path.read_bytes()


def render_schooling_certificate(student, school_year: str, principal_name: str = "") -> BytesIO:
    """Retourne le certificat PDF prêt à être envoyé par Flask."""
    output = BytesIO(_render_docx(student, school_year, principal_name))
    output.seek(0)
    return output
