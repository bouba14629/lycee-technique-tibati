import os
from types import SimpleNamespace

from censeur_routes import _is_stt_class

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def school_class(section_code, level, class_name, section_name=""):
    section = SimpleNamespace(code=section_code, name=section_name)
    department = SimpleNamespace(section=section)
    return SimpleNamespace(level=level, name=class_name, department=department)


stt_2nde = school_class("STT", "2nde", "2nde A")
stt_2nde_b = school_class("STT", "2nde", "2nde B")
stt_1ere = school_class("STT", "1ere", "1ere A")
ind_2nde = school_class("IND", "2nde", "2nde F3")
assert _is_stt_class(stt_2nde)
assert _is_stt_class(school_class("", "2nde", "2nde C", "STT"))
assert not _is_stt_class(ind_2nde)
assert stt_2nde.department.section.code == stt_2nde_b.department.section.code
assert stt_2nde.level == stt_2nde_b.level
assert stt_2nde.level != stt_1ere.level
assert ind_2nde.department.section.code != stt_2nde.department.section.code

route_source = open(os.path.join(BASE_DIR, "censeur_routes.py"), encoding="utf-8").read()
template_source = open(os.path.join(BASE_DIR, "templates/censeur_schedule.html"), encoding="utf-8").read()
assert "SchoolClass.level == current_class.level" in route_source
assert "other.level != current_class.level" in route_source
assert "not _is_stt_class(other)" not in route_source
assert "can_create_tronc_commun and tronc_commun_classes" in template_source
assert "Insérer en tronc commun" in template_source
assert "classes du même niveau" in template_source

print("SCHEDULE_STT_TRONC_COMMUN_FEATURE_TEST_OK")
