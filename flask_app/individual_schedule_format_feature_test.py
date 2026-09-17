from pathlib import Path

ROOT = Path(__file__).parent
preview = (ROOT / "templates" / "schedule_official.html").read_text(encoding="utf-8")
pdf = (ROOT / "templates" / "pdf" / "schedule_official_pdf.html").read_text(encoding="utf-8")
excel = (ROOT / "excel_utils.py").read_text(encoding="utf-8")

assert "CRÉNEAUX PLANIFIÉS" not in preview
assert "CRÉNEAUX PLANIFIÉS" not in pdf
assert "Créneaux planifiés" not in excel
assert ".schedule-compact { line-height:1; }" in preview
assert "line-height:1;" in pdf
assert "teacher.specialty or 'Enseignements généraux'" in preview
assert "teacher.specialty or 'Enseignements généraux'" in pdf
assert "DES ENSEIGNEMENTS GÉNÉRAUX" in preview
assert "DES ENSEIGNEMENTS GÉNÉRAUX" in pdf

print("INDIVIDUAL_SCHEDULE_FORMAT_FEATURE_TEST_OK")
