from io import BytesIO

from openpyxl import Workbook
from werkzeug.datastructures import FileStorage

from import_utils import read_tabular_rows


def storage(content, filename):
    return FileStorage(stream=BytesIO(content), filename=filename)


def test_csv_bom_semicolon_and_split_names():
    content = "\ufeffNom;Prénom;Code classe;Sexe\nMBOG;Jeanne;1A-ACA;F\n".encode("utf-8")
    rows = read_tabular_rows(storage(content, "eleves.csv"))
    assert rows == [(2, {
        "nom": "MBOG",
        "prenom": "Jeanne",
        "code classe": "1A-ACA",
        "sexe": "F",
    })]


def test_xlsx_ignores_leading_blank_rows_and_preserves_dates():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([])
    sheet.append(["Nom complet", "Date de naissance", "Classe"])
    sheet.append(["Paul MBOG", "2008-09-14", "1A ACA"])
    output = BytesIO()
    workbook.save(output)
    rows = read_tabular_rows(storage(output.getvalue(), "eleves.xlsx"))
    assert rows[0][0] == 3
    assert rows[0][1]["nom complet"] == "Paul MBOG"
    assert rows[0][1]["classe"] == "1A ACA"


def test_duplicate_headers_are_rejected():
    content = b"Nom complet,Nom complet\nPaul MBOG,Autre\n"
    try:
        read_tabular_rows(storage(content, "eleves.csv"))
    except ValueError as exc:
        assert "en-t\u00eates en double" in str(exc)
    else:
        raise AssertionError("Les en-t\u00eates en double doivent \u00eatre rejet\u00e9s")


if __name__ == "__main__":
    test_csv_bom_semicolon_and_split_names()
    test_xlsx_ignores_leading_blank_rows_and_preserves_dates()
    test_duplicate_headers_are_rejected()
    print("IMPORT_UTILS_REGRESSION_TEST_OK")
