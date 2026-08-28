import csv
import unicodedata
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook


MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 2000


def normalized_key(value):
    raw = str(value or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(c))


def cell_text(value):
    return str(value).strip() if value is not None else ""


def get_value(row, *names):
    for name in names:
        value = row.get(normalized_key(name))
        if value not in (None, ""):
            return cell_text(value)
    return ""


def parse_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        return value.date()
    text = cell_text(value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("date invalide — utilisez AAAA-MM-JJ ou JJ/MM/AAAA")


def read_tabular_rows(file_storage):
    filename = (file_storage.filename or "").lower()
    if not filename.endswith((".csv", ".xlsx")):
        raise ValueError("format non pris en charge — utilisez un fichier CSV ou XLSX")
    content = file_storage.read()
    if not content:
        raise ValueError("fichier vide")
    if len(content) > MAX_IMPORT_BYTES:
        raise ValueError("fichier trop volumineux (5 Mo maximum)")

    if filename.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        reader = csv.reader(text.splitlines())
        rows = list(reader)
    else:
        try:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            rows = list(workbook.active.iter_rows(values_only=True))
        except Exception as exc:
            raise ValueError("fichier XLSX illisible ou corrompu") from exc

    if not rows:
        raise ValueError("aucune ligne trouvée")
    headers = [normalized_key(v) for v in rows[0]]
    if not any(headers):
        raise ValueError("ligne d’en-tête introuvable")
    parsed = []
    for line_number, values in enumerate(rows[1:], start=2):
        if not any(v not in (None, "") for v in values):
            continue
        parsed.append((line_number, dict(zip(headers, values))))
        if len(parsed) > MAX_IMPORT_ROWS:
            raise ValueError(f"trop de lignes (maximum {MAX_IMPORT_ROWS})")
    return parsed


def import_template(kind):
    headers = {
        "enseignants": ["Nom complet", "Email", "Téléphone", "Département", "Spécialité", "Grade", "Heures dues"],
        "eleves": ["Nom complet", "Matricule", "Classe", "Sexe", "Date de naissance", "Lieu de naissance", "Redoublant"],
    }
    examples = {
        "enseignants": ["Marie NGONO", "marie.ngono@example.cm", "699000000", "ACA", "Bureautique", "PLET", 18],
        "eleves": ["Paul MBOG", "", "1A ACA", "M", "2008-09-14", "Tibati", "Non"],
    }
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Import"
    sheet.append(headers[kind])
    sheet.append(examples[kind])
    for cell in sheet[1]:
        cell.font = cell.font.copy(bold=True, color="FFFFFF")
        cell.fill = cell.fill.copy(fgColor="0B2545", fill_type="solid")
    for col in sheet.columns:
        letter = col[0].column_letter
        sheet.column_dimensions[letter].width = max(16, min(28, max(len(cell_text(c.value)) for c in col) + 3))
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
