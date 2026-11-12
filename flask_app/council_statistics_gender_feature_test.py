from types import SimpleNamespace

import utils


def main():
    students = [
        SimpleNamespace(id=1, sex="F"),
        SimpleNamespace(id=2, sex="F"),
        SimpleNamespace(id=3, sex="M"),
        SimpleNamespace(id=4, sex="M"),
    ]
    school_class = SimpleNamespace(students=students)
    averages = {1: 12.0, 2: 2.9, 3: 16.0, 4: None}
    original = utils._fast_overall_averages
    utils._fast_overall_averages = lambda *args, **kwargs: averages
    try:
        stats = utils.class_statistics(school_class, "Trimestre 1")
    finally:
        utils._fast_overall_averages = original

    # Inscrits - non classés : Filles 2-1=1, Garçons 2-0=2, Total 4-1=3.
    assert stats["inscrits"] == {"F": 2, "G": 2, "T": 4}
    assert stats["non_classes"] == {"F": 1, "G": 0, "T": 1}
    assert stats["evalues"] == {"F": 1, "G": 2, "T": 3}
    # Le tableau d’honneur commence à 12/20, et non à 16/20.
    assert stats["th"] == {"F": 1, "G": 1, "T": 2}
    assert stats["reussite"] == {"F": 1, "G": 1, "T": 2}

    original_class_statistics = utils.class_statistics
    fake_class = SimpleNamespace(level="1A")
    utils.class_statistics = lambda *args, **kwargs: {
        "class": fake_class,
        "inscrits": {"F": 2, "G": 2, "T": 4},
        "evalues": {"F": 1, "G": 2, "T": 3},
        "non_classes": {"F": 1, "G": 0, "T": 1},
        "reussite": {"F": 1, "G": 1, "T": 2},
        "th": {"F": 1, "G": 1, "T": 2},
        "encouragement": {"F": 0, "G": 0, "T": 0},
        "felicitations": {"F": 0, "G": 1, "T": 1},
        "pct": {"F": 100, "G": 50, "T": 66.67},
        "_avgs_by_id": {1: 12.0, 2: 2.9, 3: 16.0, 4: None},
        "forte_moyenne": {"F": 12.0, "G": 16.0},
        "faible_moyenne": {"F": 12.0, "G": 16.0},
        "moyenne_generale": 14.0,
        "observation": "",
    }
    try:
        aggregate = utils.council_statistics([fake_class], "Trimestre 1")["total_general"]
    finally:
        utils.class_statistics = original_class_statistics
    assert aggregate["moyenne_generale"] == 14.0
    print("COUNCIL_STATISTICS_GENDER_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
