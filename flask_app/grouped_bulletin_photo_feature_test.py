from pathlib import Path

listing = Path(__file__).parent / "templates/censeur_bulletins.html"
grouped = Path(__file__).parent / "templates/pdf/class_bulletins_pdf.html"
body = Path(__file__).parent / "templates/pdf/_bulletin_body.html"
listing_text = listing.read_text(encoding="utf-8")
grouped_text = grouped.read_text(encoding="utf-8")
body_text = body.read_text(encoding="utf-8")

assert "Consultez et imprimez le bulletin d'un élève" not in listing_text
assert "Inclus dans <strong>Imprimer tous</strong>" in listing_text
assert "student_photo_path=(row.photo_path or avatar_path)" in grouped_text
assert "student_photo_path=row.photo_path" not in grouped_text
assert 'class="title-table"' in body_text
assert 'class="photo-box"' in body_text
assert "{{ student.full_name }}" in body_text
photo_position = body_text.index('class="photo-box"')
name_position = body_text.index("{{ student.full_name }}", photo_position)
assert photo_position < name_position
print("GROUPED_BULLETIN_PHOTO_FEATURE_TEST_OK")
