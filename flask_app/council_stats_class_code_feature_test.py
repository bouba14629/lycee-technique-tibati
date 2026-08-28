from pathlib import Path


def main():
    root = Path(__file__).parent
    template = (root / "templates" / "censeur_council_stats.html").read_text(encoding="utf-8")
    export = (root / "excel_utils.py").read_text(encoding="utf-8")

    assert '<th rowspan="2">Code</th>' in template
    assert "school_class.code or 'Sans code'" in template
    assert "school_class.name" not in template
    assert 'groups = [("CODE", 1, 1)' in export
    assert "row['class'].code or 'Sans code', row" in export
    assert "row['class'].code or 'Sans code'} — {row['class'].name}" not in export
    print("COUNCIL_STATS_CLASS_CODE_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
