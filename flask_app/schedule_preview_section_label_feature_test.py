from pathlib import Path


def main():
    template = Path(__file__).with_name("templates").joinpath("schedule_official.html").read_text(encoding="utf-8")
    assert "<strong>SECTION" not in template
    assert "{{ school_class.department.section.code }}" in template
    print("SCHEDULE_PREVIEW_SECTION_LABEL_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
