import os


def main():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dir_structure.html")
    with open(template_path, encoding="utf-8") as template_file:
        content = template_file.read()

    assert "Préparation des bulletins" not in content
    assert "Créer une section" in content
    assert "Ajouter une filière" in content
    print("STRUCTURE_BULLETIN_HINT_REMOVAL_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
