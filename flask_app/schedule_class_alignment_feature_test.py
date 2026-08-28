from pathlib import Path


def test_class_is_centered_between_section_and_school_year():
    template = Path(__file__).with_name("templates").joinpath("pdf", "schedule_official_pdf.html").read_text(encoding="utf-8")
    assert '<td style="width:30%; text-align:left; padding-right:24pt;"><span class="red">{{ section_label }}</span></td>' in template
    assert '<td style="width:40%; text-align:center; padding-left:24pt; padding-right:24pt;"><strong>CLASSE' in template
    assert '<td style="width:30%; text-align:right; padding-left:24pt;"><strong>ANNÉE SCOLAIRE' in template
    preview = Path(__file__).with_name("templates").joinpath("schedule_official.html").read_text(encoding="utf-8")
    assert 'table-layout:fixed' in preview
    assert 'width:30%; text-align:left; padding-right:24px;' in preview
    assert 'width:40%; text-align:center; padding-left:24px; padding-right:24px;' in preview


if __name__ == "__main__":
    test_class_is_centered_between_section_and_school_year()
    print("SCHEDULE_CLASS_ALIGNMENT_FEATURE_TEST_OK")
