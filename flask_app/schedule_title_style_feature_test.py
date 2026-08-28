from pathlib import Path


def test_schedule_title_is_not_underlined():
    template = Path(__file__).with_name("templates").joinpath("pdf", "schedule_official_pdf.html").read_text(encoding="utf-8")
    assert ".title" in template
    assert "text-decoration:none" in template
    assert "text-decoration:underline" not in template
    title_table_rule = next(line for line in template.splitlines() if ".title-table" in line)
    assert "border: 0" in title_table_rule
    assert "border-top: 0" in title_table_rule
    assert "border-bottom: 0" in title_table_rule
    assert ".title-table td { border: 0; border-top: 0; border-bottom: 0; }" in template
    assert "text-decoration:none; border:0;" in template
    assert 'class="title-table" style="border:0; border-top:0; border-bottom:0;"' in template


if __name__ == "__main__":
    test_schedule_title_is_not_underlined()
    print("SCHEDULE_TITLE_STYLE_FEATURE_TEST_OK")
