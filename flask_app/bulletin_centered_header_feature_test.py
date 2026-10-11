from pathlib import Path

ROOT = Path(__file__).parent
body = (ROOT / "templates" / "pdf" / "_bulletin_body.html").read_text(encoding="utf-8")
individual = (ROOT / "templates" / "pdf" / "bulletin_pdf.html").read_text(encoding="utf-8")
grouped = (ROOT / "templates" / "pdf" / "class_bulletins_pdf.html").read_text(encoding="utf-8")
pdf_utils = (ROOT / "pdf_utils.py").read_text(encoding="utf-8")

assert 'width:54%; text-align:center; vertical-align:middle;' in body
assert 'width:23%; text-align:center; vertical-align:middle;' in body
assert 'BULLETIN DU {{ term_ordinal }} TRIMESTRE' in body
assert 'SECTION {{ student.school_class.department.section.name|upper' in body
assert '<img src="{{ logo_path }}" width="64"/>' in body
assert '{% include "pdf/_bulletin_body.html" %}' in individual
assert '{% include "pdf/_bulletin_body.html" %}' in grouped
assert 'embedded_logo = pdf_image_data_uri(logo_path)' in pdf_utils
assert 'context.setdefault("logo_path", embedded_logo)' in pdf_utils

print("BULLETIN_CENTERED_HEADER_FEATURE_TEST_OK")
