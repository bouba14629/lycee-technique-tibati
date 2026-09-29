from pathlib import Path


template = (Path(__file__).parent / "templates" / "censeur_teacher_service.html").read_text(encoding="utf-8")

assert ".service-table tr.day-start > th,.service-table tr.day-start > td { border-top-width:2px; }" in template
assert ".service-table tr.day-end > th,.service-table tr.day-end > td { border-bottom-width:2px; }" in template
assert "border-top-width:2px; border-bottom-width:2px;" in template
assert "'day-start' if index == 0" in template
assert "'day-end' if index == periods|length - 1" in template

print("TEACHER_SERVICE_DAY_SEPARATOR_FEATURE_TEST_OK")
