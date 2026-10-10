from pathlib import Path

ROOT = Path(__file__).parent
route = (ROOT / "censeur_routes.py").read_text(encoding="utf-8")
listing = (ROOT / "templates" / "censeur_teacher_schedule_list.html").read_text(encoding="utf-8")
bulk = (ROOT / "templates" / "pdf" / "schedule_official_bulk_pdf.html").read_text(encoding="utf-8")
official = (ROOT / "templates" / "pdf" / "schedule_official_pdf.html").read_text(encoding="utf-8")

assert "censeur_teacher_schedule_bulk_pdf" in route
assert '"pdf/schedule_official_bulk_pdf.html"' in route
assert 'download_name="Emplois_du_temps_individuels.pdf"' in route
assert "Imprimer Tous" in listing
assert "url_for('censeur_teacher_schedule_bulk_pdf')" in listing
assert "for item in schedules" in bulk
assert "page-break-after:" in bulk
assert "EMPLOI DE TEMPS INDIVIDUEL" in bulk
assert "logo_path" in bulk
assert bulk.count("page-break-inside: avoid") >= official.count("page-break-inside: avoid")
assert "teacher_hours_faites" in route
assert "teacher_extra_hours" in route

print("CENSEUR_TEACHER_SCHEDULE_BULK_PRINT_FEATURE_TEST_OK")
