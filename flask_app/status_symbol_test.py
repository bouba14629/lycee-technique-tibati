from pathlib import Path

template_dir = Path(__file__).parent / "templates"
attendance = (template_dir / "attendance_sheet.html").read_text(encoding="utf-8")
bulletin = (template_dir / "bulletin.html").read_text(encoding="utf-8")

assert "bi-square" not in attendance
assert "bi-square" not in bulletin
assert "attendance-mark" in attendance
assert "bulletin-mark" in bulletin
assert "✓" in attendance
assert "○" in bulletin

print("STATUS_SYMBOL_TEST_OK")
