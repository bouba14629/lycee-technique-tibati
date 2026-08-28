from pathlib import Path


def test_director_dashboard_does_not_show_pilotage_establishment_label():
    template = Path(__file__).with_name("templates").joinpath("dashboard_directeur.html").read_text(encoding="utf-8")
    assert "Pilotage de l’établissement" not in template
    assert "Une vue claire pour décider, organiser et suivre." not in template
    assert "dashboard-hero" not in template
    assert "Démarrage de l’établissement" in template


if __name__ == "__main__":
    test_director_dashboard_does_not_show_pilotage_establishment_label()
    print("DIRECTOR_DASHBOARD_PILOTAGE_REMOVAL_FEATURE_TEST_OK")
