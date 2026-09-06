from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


NAVY = "0B2545"
GOLD = "C9A227"
CREAM = "F8F5EC"
THIN = Side(style="thin", color="D9D0B0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def import_report_workbook(report):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rapport d’import"
    detailed = any(isinstance(error, dict) for error in report.get("errors", []))
    if detailed:
        widths = {"A": 12, "B": 24, "C": 54, "D": 68}
    else:
        widths = {"A": 26, "B": 88}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(widths))
    title = sheet["A1"]
    title.value = "LYCÉE TECHNIQUE DE TIBATI — RAPPORT D’IMPORT"
    title.font = Font(bold=True, size=13, color="FFFFFF")
    title.fill = PatternFill("solid", fgColor=NAVY)
    title.alignment = Alignment(horizontal="center")
    sheet["A3"] = "Type d’import"; sheet["B3"] = report.get("kind", "—").capitalize()
    sheet["A4"] = "Lignes importées"; sheet["B4"] = report.get("created", 0)
    sheet["A5"] = "Lignes ignorées"; sheet["B5"] = report.get("skipped", 0)
    for row in range(3, 6):
        sheet.cell(row=row, column=1).font = Font(bold=True, color=NAVY)
    if detailed:
        headers = ["Ligne", "Champ", "Problème", "Correction recommandée"]
    else:
        headers = ["Statut", "Détail"]
    for index, header in enumerate(headers, start=1):
        sheet.cell(row=7, column=index, value=header)
    for cell in sheet[7][:len(headers)]:
        cell.font = Font(bold=True, color=NAVY)
        cell.fill = PatternFill("solid", fgColor=CREAM)
        cell.border = BORDER
    errors = report.get("errors", [])
    if errors:
        for row_number, error in enumerate(errors, start=8):
            values = ([error.get("line", "—"), error.get("field", "—"), error.get("cause", "—"), error.get("correction", "—")]
                      if isinstance(error, dict) else ["—", "—", error, ""])
            for column, value in enumerate(values, start=1):
                sheet.cell(row=row_number, column=column, value=value).border = BORDER
    else:
        sheet.cell(row=8, column=1, value="Conforme").border = BORDER
        sheet.cell(row=8, column=2, value="Aucune ligne à corriger.").border = BORDER
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
