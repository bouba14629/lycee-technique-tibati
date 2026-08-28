from types import SimpleNamespace

from utils import schedule_group_labels


def entry(entry_id, group_key, level, section_code, class_name):
    section = SimpleNamespace(code=section_code)
    department = SimpleNamespace(section=section)
    school_class = SimpleNamespace(level=level, name=class_name, department=department)
    return SimpleNamespace(id=entry_id, group_key=group_key, course=SimpleNamespace(school_class=school_class))


stt_entries = [entry(1, "stt", "Tles", "STT", "Tles A"), entry(2, "stt", "Tles", "STT", "Tles B")]
ind_entries = [entry(3, "ind", "Tles", "IND", "Tles F1"), entry(4, "ind", "Tles", "IND", "Tles F2")]
joint_entries = [entry(5, "both", "Tles", "STT", "Tles A"), entry(6, "both", "Tles", "IND", "Tles F1")]
single_entry = [entry(7, None, "Tles", "STT", "Tles ACA")]

assert set(schedule_group_labels(stt_entries).values()) == {"Tles (STT)"}
assert set(schedule_group_labels(ind_entries).values()) == {"Tles (IND)"}
assert set(schedule_group_labels(joint_entries).values()) == {"Tles"}
assert schedule_group_labels(single_entry)[7] == "Tles ACA"

schedule_pdf = open("templates/pdf/schedule_official_pdf.html", encoding="utf-8").read()
assert "font-size: 9pt; height: 46pt" in schedule_pdf
assert ".subj { font-weight: bold; font-size: 9pt" in schedule_pdf
assert ".teach { font-style: italic; color: #666; font-size: 7.4pt" in schedule_pdf

print("SCHEDULE_GROUPING_FEATURE_TEST_OK")
