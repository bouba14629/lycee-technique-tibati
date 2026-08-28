from pathlib import Path


def main():
    root = Path(__file__).with_name("templates")
    pdf_template = root.joinpath("pdf", "schedule_official_pdf.html").read_text(encoding="utf-8")
    preview_template = root.joinpath("schedule_official.html").read_text(encoding="utf-8")

    assert '<img src="{{ logo_path }}" width="100"/>' in pdf_template
    assert "filename='img/logo.svg') }}\" width=\"100\"" in preview_template
    print("SCHEDULE_LOGO_SIZE_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
