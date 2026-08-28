from pathlib import Path


def test_schedule_footer_has_no_signature_lines_or_date_dots():
    template = Path(__file__).with_name("templates").joinpath("pdf", "schedule_official_pdf.html").read_text(encoding="utf-8")
    preview = Path(__file__).with_name("templates").joinpath("schedule_official.html").read_text(encoding="utf-8")
    assert ".footer-table td" in template
    assert "border-top: 0.65pt solid #ccc" not in template
    assert ".footer-table tr, .footer-table td { border: 0; border-top: 0; border-bottom: 0;" in template
    assert 'class="footer-table" style="margin-top:8pt; border:0; border-top:0; border-bottom:0;"' in template
    assert "TIBATI, le ______" not in template
    assert "TIBATI, le</div>" in template
    assert "border-top:1px dashed #e2dac0" not in preview
    assert "border-top:1px solid #ccc" not in preview
    assert 'style="border-top:0;"' in preview
    assert 'class="col-6 text-start"' in preview
    assert 'text-align:left; padding-left:0;' in template


if __name__ == "__main__":
    test_schedule_footer_has_no_signature_lines_or_date_dots()
    print("SCHEDULE_FOOTER_CLEANUP_FEATURE_TEST_OK")
