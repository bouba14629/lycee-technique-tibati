from pathlib import Path

from utils import competency_marks


CASES = {
    9.99: {"travail_insuffisant"},
    10.0: {"bon_travail"},
    11.99: {"bon_travail"},
    12.0: {"tableau_honneur", "travail_passable"},
    13.99: {"tableau_honneur", "travail_passable"},
    14.0: {"tableau_honneur", "encouragements", "travail_passable"},
    15.99: {"tableau_honneur", "encouragements", "travail_passable"},
    16.0: {"tableau_honneur", "encouragements", "felicitations", "assez_bon_travail"},
    20.0: {"tableau_honneur", "encouragements", "felicitations", "assez_bon_travail"},
}

for average, expected in CASES.items():
    marks = competency_marks(average)
    actual = {key for key, checked in marks.items() if checked}
    assert actual == expected, (average, actual, expected)

assert not any(competency_marks(value)["travail_insuffisant"] for value in (10.0, 12.0, 14.0, 16.0))
assert competency_marks(None) == {key: False for key in competency_marks(0)}

body = Path(__file__).with_name("templates") / "pdf" / "_bulletin_body.html"
source = body.read_text(encoding="utf-8")
assert "Avert. Travail" not in source
assert "Compétences non acquises" in source
assert "Compétences moyennement acquises" in source
assert "Compétences bien acquises" in source
assert "Compétences très bien acquises" in source

print("BULLETIN_COMPETENCY_THRESHOLDS_FEATURE_TEST_OK")
