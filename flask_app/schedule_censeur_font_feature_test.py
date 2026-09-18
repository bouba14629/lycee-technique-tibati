from pathlib import Path

ROOT = Path(__file__).parent
routes = (ROOT / "censeur_routes.py").read_text(encoding="utf-8")
screen = (ROOT / "templates" / "schedule_official.html").read_text(encoding="utf-8")
pdf = (ROOT / "templates" / "pdf" / "schedule_official_pdf.html").read_text(encoding="utf-8")

assert 'can_build_schedule = user.role == "directeur" or user.role in {"censeur", "censeur_crm"}' in routes
assert 'can_create_tronc_commun = bool(current_class) and can_build_schedule' in routes
assert 'user_scoped_class_ids(user) if user.role == "censeur" else None' in routes
assert 'user.role == "censeur_crm"' in routes
assert 'font-size:12.5px; max-width:100%;' in screen
assert 'font-size:14px;' in screen
assert 'font-size:12.5px;' in screen
assert 'font-size:11.5px; color:#000; font-style:italic;' in screen
assert 'body { font-family: \'Inter\', Helvetica, sans-serif; color: #000; font-size: 11.5pt; line-height:1.5; }' in pdf
assert '.red { color: #000000; font-weight: bold; }' in pdf
assert 'page-break-inside: avoid' in pdf
assert 'color:#c0392b' not in screen
assert 'font-size: 12pt;' in pdf
assert 'font-size: 10.4pt;' in pdf

print("SCHEDULE_CENSEUR_FONT_FEATURE_TEST_OK")
