from pathlib import Path


template = Path(__file__).with_name("templates").joinpath("login.html").read_text(encoding="utf-8")

required_labels = [
    "Accueil",
    "La Cité Scolaire",
    "Le Mot du Chef d’Établissement",
    "Résultats",
    "Informations",
    "Liste des Fournitures",
    "Inscriptions",
    "Services",
    "Bibliothèque",
    "Censorat",
    "Chef des Travaux",
    "Orientation Scolaire et Professionnelle",
    "Surveillance Générale",
    "CRM",
    "Départements",
    "Français",
    "Anglais",
    "Histoire-Géographie-ECM",
    "Hygiène",
    "Sciences Physiques",
    "Philosophie",
    "Mathématiques",
    "Informatique",
    "Génie Electrique",
    "Génie Civil",
    "Génie Bois",
    "Industrie de l’Habillement",
    "Comptabilité et Gestion",
    "FIG",
    "ACA",
    "ESF",
    "Economie",
    "APPS",
    "Club Informatique",
    "Club Scout",
    "Club Génie Electrique",
    "Club Majorette",
    "Club Tourisme",
    "Contact",
]

for label in required_labels:
    assert label in template, label

for anchor in ["public-accueil", "connexion"]:
    assert f'id="{anchor}"' in template, anchor

assert '<form method="POST" class="form-ltt">' in template
assert 'name="username"' in template and 'name="password"' in template
assert template.count("<details>") == 5
assert 'role="button" aria-haspopup="menu"' in template
assert "other.removeAttribute('open')" in template
assert "'.public-home-nav-links > a'" in template
assert "'.public-home-nav-links details[open]'" in template
assert "public-home-info" not in template
print("HOME_PUBLIC_NAVIGATION_FEATURE_TEST_OK")
