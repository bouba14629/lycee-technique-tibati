from pathlib import Path


def test_global_back_button_is_available_in_the_common_layout():
    template = Path(__file__).with_name("templates").joinpath("base.html").read_text(encoding="utf-8")
    assert "data-app-back" in template
    assert "Retour à la rubrique précédente" in template
    assert "returnToPreviousRubrique" in template
    assert "if (window.history.length > 1)" in template
    assert "window.history.back()" in template
    assert "url_for('dashboard')" in template
    assert "document.referrer" not in template
    assert "contextmenu" in template
    assert "event.preventDefault()" in template


if __name__ == "__main__":
    test_global_back_button_is_available_in_the_common_layout()
    print("GLOBAL_BACK_BUTTON_FEATURE_TEST_OK")
