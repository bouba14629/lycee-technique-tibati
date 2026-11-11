from pathlib import Path

listing = Path(__file__).parent / "templates/censeur_bulletins.html"
grouped = Path(__file__).parent / "templates/pdf/class_bulletins_pdf.html"
annual_grouped = Path(__file__).parent / "templates/pdf/class_annual_bulletins_pdf.html"
body = Path(__file__).parent / "templates/pdf/_bulletin_body.html"
listing_text = listing.read_text(encoding="utf-8")
grouped_text = grouped.read_text(encoding="utf-8")
annual_grouped_text = annual_grouped.read_text(encoding="utf-8")
body_text = body.read_text(encoding="utf-8")
bulletin_pdf = (Path(__file__).parent / "templates/pdf/bulletin_pdf.html").read_text(encoding="utf-8")

assert "Consultez et imprimez le bulletin d'un élève" not in listing_text
assert "Inclus dans <strong>Imprimer tous</strong>" in listing_text
assert "student_photo_path=(row.photo_path or avatar_path)" in grouped_text
assert "preview=1" in listing_text
assert "as_attachment=not inline_preview" in (Path(__file__).parent / "censeur_routes.py").read_text(encoding="utf-8")
assert "as_attachment=not inline_preview" in (Path(__file__).parent / "eleve_routes.py").read_text(encoding="utf-8")
assert "border-top: 0" in grouped_text and "border-top: 0" in bulletin_pdf
assert "student_photo_path=row.photo_path" not in grouped_text
assert 'class="title-table"' in body_text
assert 'class="student-photo-placement"' in body_text
assert '{{ logo_path or bulletin_logo_path }}' in body_text
assert 'logo_path=(logo_path or bulletin_logo_path)' in grouped_text
assert 'bulletin_logo_path=bulletin_logo_path' in grouped_text
assert 'bulletin_logo_path=(bulletin_logo_path or logo_path)' in annual_grouped_text
assert 'student_photo_path=(item.photo_path or avatar_path)' in annual_grouped_text
assert 'photo_source = get_student_photo_source(st)' in (Path(__file__).parent / "censeur_routes.py").read_text(encoding="utf-8")
assert 'mimetypes.guess_type(path)' in (Path(__file__).parent / "pdf_utils.py").read_text(encoding="utf-8")
assert "{{ student.full_name }}" in body_text
photo_position = body_text.index('class="student-photo-placement"')
name_position = body_text.index("{{ student.full_name }}")
assert name_position < photo_position
print("GROUPED_BULLETIN_PHOTO_FEATURE_TEST_OK")
