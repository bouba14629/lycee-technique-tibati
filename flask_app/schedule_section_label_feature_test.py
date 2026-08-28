from pathlib import Path


def test_industrial_section_uses_full_label_in_schedule():
    template = Path(__file__).with_name("templates").joinpath("pdf", "schedule_official_pdf.html").read_text(encoding="utf-8")
    assert "{% set section_label = school_class.department.section.name|upper|replace('SECTION ', '')" in template
    assert "{% set censeur_label = 'INDUSTRIEL' if section_label == 'INDUSTRIELLE' else section_label %}" in template
    assert "<span class=\"red\">{{ section_label }}</span>" in template
    assert "<strong>SECTION" not in template
    assert "LE CENSEUR {{ censeur_label }}" in template
    assert "school_class.department.section.code" not in template


if __name__ == "__main__":
    test_industrial_section_uses_full_label_in_schedule()
    print("SCHEDULE_SECTION_LABEL_FEATURE_TEST_OK")
