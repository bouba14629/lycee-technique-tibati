import random
from datetime import date, datetime
from io import BytesIO
import os
import random
import re
import tempfile
import uuid
import zipfile

from flask import abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.datastructures import FileStorage

from app import app, db
from directeur_routes import gen_username, save_student_photo
from import_utils import get_value, import_template, parse_date, read_tabular_rows
from import_report_utils import import_report_workbook
from models import Department, SchoolClass, Student, Teacher, User
from utils import roles_required, generate_account_password


@app.context_processor
def inject_import_departments():
    return {"import_departments": Department.query.order_by(Department.name).all()}


@app.route("/directeur/imports/modele/<kind>.xlsx")
@roles_required("directeur")
def import_template_download(kind):
    if kind not in ("enseignants", "eleves"):
        abort(404)
    return send_file(import_template(kind), as_attachment=True,
                     download_name=f"modele_import_{kind}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/directeur/imports/rapport")
@roles_required("directeur")
def import_report():
    return render_template("import_report.html", report=session.get("last_import_report"))


def _last_import_report():
    report = session.get("last_import_report")
    if not report:
        flash("Aucun rapport d’import disponible pour cette session.", "warning")
        return None
    return report


@app.route("/directeur/imports/rapport.xlsx")
@roles_required("directeur")
def import_report_excel():
    report = _last_import_report()
    if not report:
        return redirect(url_for("import_report"))
    return send_file(import_report_workbook(report), as_attachment=True,
                     download_name=f"rapport_import_{report['kind']}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/directeur/imports/rapport.pdf")
@roles_required("directeur")
def import_report_pdf():
    report = _last_import_report()
    if not report:
        return redirect(url_for("import_report"))
    from pdf_utils import render_pdf
    pdf = render_pdf("pdf/import_report_pdf.html", report=report)
    if not pdf:
        flash("Le rapport PDF n’a pas pu être généré. Réessayez plus tard.", "danger")
        return redirect(url_for("import_report"))
    return send_file(pdf, as_attachment=True, download_name=f"rapport_import_{report['kind']}.pdf",
                     mimetype="application/pdf")


def _store_report(kind, created, skipped, errors):
    session["last_import_report"] = {
        "kind": kind,
        "created": created,
        "skipped": skipped,
        "errors": errors[:30],
        "has_more": len(errors) > 30,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def _teacher_full_name(row):
    """Accepte un nom complet ou les colonnes distinctes Nom et Prénom."""
    full_name = get_value(row, "nom complet", "noms et prenoms", "nom et prenom")
    if full_name:
        return " ".join(full_name.split())
    last_name = get_value(row, "nom", "nom de famille", "noms")
    first_name = get_value(row, "prenom", "prenoms", "prenom(s)")
    return " ".join(part for part in (last_name, first_name) if part)


def _photo_key(value):
    """Normalise un matricule ou nom de fichier pour associer une photo sans ambiguïté visuelle."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _read_photo_archive(path):
    """Retourne les photos admissibles d'une archive ZIP, indexées par matricule ou nom de fichier."""
    if not path or not os.path.exists(path):
        return {}
    photos = {}
    with zipfile.ZipFile(path) as archive:
        image_names = [name for name in archive.namelist() if not name.endswith("/") and
                       os.path.splitext(name)[1].lower().lstrip(".") in {"jpg", "jpeg", "png", "webp"}]
        if len(image_names) > 500:
            raise ValueError("l’archive contient trop de photos (maximum : 500)")
        for name in image_names:
            info = archive.getinfo(name)
            if info.file_size > 5 * 1024 * 1024:
                continue
            stem = os.path.splitext(os.path.basename(name))[0]
            key = _photo_key(stem)
            if key and key not in photos:
                photos[key] = (os.path.basename(name), archive.read(name))
    return photos


def _student_full_name(row):
    """Accepte Nom complet ou les colonnes distinctes Nom et Prénom."""
    full_name = get_value(row, "nom complet", "noms et prenoms", "nom et prenom", "eleve")
    if full_name:
        return " ".join(full_name.split())
    last_name = get_value(row, "nom", "nom de famille", "noms")
    first_name = get_value(row, "prenom", "prenoms", "prenom s")
    return " ".join(part for part in (first_name, last_name) if part)


def _class_lookup():
    """Indexe les classes par nom et par code sans écraser les homonymes."""
    lookup = {}
    for school_class in SchoolClass.query.join(Department).all():
        for value in (school_class.name, school_class.code):
            key = value and value.strip().lower()
            if key:
                lookup.setdefault(key, []).append(school_class)
    return lookup


def _resolve_student_class(class_ref, classes_by_identifier, department_id=None):
    if not class_ref:
        return None, "classe requise ou introuvable"
    candidates = classes_by_identifier.get(class_ref.strip().lower(), [])
    if department_id:
        candidates = [school_class for school_class in candidates
                      if school_class.department_id == department_id]
    if not candidates:
        return None, f"classe introuvable ({class_ref})"
    if len(candidates) > 1:
        return None, f"classe ambiguë ({class_ref}) — utilisez le code de classe"
    return candidates[0], None


def _student_sex(value):
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"m", "masculin", "homme", "garcon", "garçon"}:
        return "M"
    if normalized in {"f", "feminin", "féminin", "femme", "fille"}:
        return "F"
    return "INVALID"


def _preview_student_rows(rows, chosen_class, classes_by_identifier=None, department_id=None):
    """Construit une prévisualisation légère, sans créer aucun compte ni élève."""
    classes_by_identifier = classes_by_identifier or _class_lookup()
    preview, errors = [], []
    seen_matricules = set()
    for line_number, row in rows[:100]:
        full_name = _student_full_name(row)
        if not full_name:
            errors.append(f"Ligne {line_number} : renseignez « Nom complet » ou « Nom » et « Prénom ».")
            continue
        class_ref = get_value(row, "classe", "classe scolaire", "code classe")
        school_class = chosen_class
        if not school_class and class_ref:
            school_class, class_error = _resolve_student_class(class_ref, classes_by_identifier, department_id)
            if class_error:
                errors.append(f"Ligne {line_number} : {class_error}.")
                continue
        if not school_class:
            errors.append(f"Ligne {line_number} : sélectionnez une classe ou renseignez la colonne « Classe ».")
            continue
        sex = _student_sex(get_value(row, "sexe", "genre"))
        if sex == "INVALID":
            errors.append(f"Ligne {line_number} : sexe invalide — utilisez M ou F.")
            continue
        try:
            parse_date(get_value(row, "date de naissance", "naissance", "date naissance"))
        except ValueError as exc:
            errors.append(f"Ligne {line_number} : {exc}.")
            continue
        requested_matricule = get_value(row, "matricule", "matricule scolaire")
        if requested_matricule and (requested_matricule in seen_matricules or
                                    Student.query.filter_by(matricule=requested_matricule).first()):
            errors.append(f"Ligne {line_number} : matricule déjà utilisé ({requested_matricule}).")
            continue
        if requested_matricule:
            seen_matricules.add(requested_matricule)
        preview.append({"line": line_number, "full_name": full_name,
                        "matricule": requested_matricule or "Automatique",
                        "class_name": school_class.name,
                        "department_name": school_class.department.name,
                        "photo_found": False})
    return preview, errors


def teachers_import_v2():
    file = request.files.get("import_file")
    if not file or not file.filename:
        flash("Veuillez sélectionner un fichier CSV ou XLSX.", "warning")
        return redirect(url_for("dir_users"))
    try:
        rows = read_tabular_rows(file)
    except ValueError as exc:
        flash(f"Import impossible : {exc}.", "danger")
        return redirect(url_for("dir_users"))

    departments_by_code = {department.code.strip().lower(): department for department in Department.query.all()}
    default_department_id = request.form.get("department_id", type=int)
    default_department = Department.query.get(default_department_id) if default_department_id else None
    created, skipped, errors = 0, 0, []

    for line_number, row in rows:
        full_name = _teacher_full_name(row)
        if not full_name:
            skipped += 1; errors.append(f"Ligne {line_number} : renseignez « Nom complet » ou les colonnes « Nom » et « Prénom »."); continue
        email = get_value(row, "email")
        phone = get_value(row, "téléphone", "telephone", "tel", "phone")
        department_code = get_value(row, "département", "departement", "filiere")
        department = departments_by_code.get(department_code.lower()) if department_code else default_department
        if not department:
            skipped += 1; errors.append(f"Ligne {line_number} : département requis ou introuvable."); continue
        if email and User.query.filter_by(email=email).first():
            skipped += 1; errors.append(f"Ligne {line_number} : email déjà utilisé ({email})."); continue
        try:
            hours_due = int(get_value(row, "heures dues", "heures") or 18)
        except ValueError:
            skipped += 1; errors.append(f"Ligne {line_number} : heures dues invalides."); continue
        username = gen_username(full_name)
        password = generate_account_password(full_name, "enseignant")
        user = User(username=username, role="enseignant", full_name=full_name, email=email, phone=phone,
                    must_change_password=True)
        user.set_password(password)
        db.session.add(user); db.session.flush()
        db.session.add(Teacher(user_id=user.id, department_id=department.id,
                               specialty=get_value(row, "spécialité", "specialite", "matiere") or department.name,
                               grade=get_value(row, "grade") or "PLET", hours_due=hours_due,
                               hire_date=date.today()))
        created += 1

    db.session.commit()
    _store_report("enseignants", created, skipped, errors)
    flash(f"{created} enseignant(s) importé(s). {skipped} ligne(s) ignorée(s).", "success" if created else "warning")
    if errors:
        flash("Consultez le rapport d’import pour corriger les lignes ignorées.", "warning")
    return redirect(url_for("dir_users"))


def students_import_v2(rows=None, photo_files=None, chosen_class_id=None, chosen_department_id=None):
    if rows is None:
        file = request.files.get("import_file")
        if not file or not file.filename:
            flash("Veuillez sélectionner un fichier CSV ou XLSX.", "warning")
            return redirect(url_for("student_enroll"))
        try:
            rows = read_tabular_rows(file)
        except ValueError as exc:
            flash(f"Import impossible : {exc}.", "danger")
            return redirect(url_for("student_enroll"))

    if chosen_class_id is None:
        chosen_class_id = request.form.get("class_id", type=int)
    if chosen_department_id is None:
        chosen_department_id = request.form.get("department_id", type=int)
    chosen_class = SchoolClass.query.get(chosen_class_id) if chosen_class_id else None
    if chosen_class_id and not chosen_class:
        flash("La classe cible sélectionnée est introuvable.", "danger")
        return redirect(url_for("student_enroll"))
    if chosen_class and chosen_department_id and chosen_class.department_id != chosen_department_id:
        flash("La classe cible ne relève pas de la filière sélectionnée.", "danger")
        return redirect(url_for("student_enroll"))

    classes_by_identifier = _class_lookup()
    created, skipped, errors = 0, 0, []
    seen_matricules = set()

    for line_number, row in rows:
        full_name = _student_full_name(row)
        if not full_name:
            skipped += 1
            errors.append(f"Ligne {line_number} : renseignez « Nom complet » ou « Nom » et « Prénom ».")
            continue

        class_ref = get_value(row, "classe", "classe scolaire", "code classe")
        school_class = chosen_class
        if not school_class:
            school_class, class_error = _resolve_student_class(class_ref, classes_by_identifier, chosen_department_id)
            if class_error:
                skipped += 1
                errors.append(f"Ligne {line_number} : {class_error}.")
                continue
        elif chosen_department_id and school_class.department_id != chosen_department_id:
            skipped += 1
            errors.append(f"Ligne {line_number} : classe hors de la filière sélectionnée.")
            continue

        sex = _student_sex(get_value(row, "sexe", "genre"))
        if sex == "INVALID":
            skipped += 1
            errors.append(f"Ligne {line_number} : sexe invalide — utilisez M ou F.")
            continue
        try:
            dob = parse_date(get_value(row, "date de naissance", "naissance", "date naissance"))
        except ValueError as exc:
            skipped += 1
            errors.append(f"Ligne {line_number} : {exc}.")
            continue

        requested_matricule = get_value(row, "matricule", "matricule scolaire")
        if requested_matricule and (requested_matricule in seen_matricules or
                                    Student.query.filter_by(matricule=requested_matricule).first()):
            skipped += 1
            errors.append(f"Ligne {line_number} : matricule déjà utilisé ({requested_matricule}).")
            continue
        matricule = requested_matricule or f"LTT{date.today().year}{random.randint(1000, 9999)}"
        while matricule in seen_matricules or Student.query.filter_by(matricule=matricule).first():
            matricule = f"LTT{date.today().year}{random.randint(1000, 9999)}"
        seen_matricules.add(matricule)

        first_name, last_name = (full_name.split(" ", 1) + [""])[:2]
        username = gen_username(full_name)
        password = generate_account_password(full_name, "eleve")
        user = User(username=username, role="eleve", full_name=full_name, must_change_password=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        repeater_value = get_value(row, "redoublant", "statut redoublant", "repeater").strip().lower()
        is_repeater = repeater_value in {"oui", "o", "1", "true", "vrai", "redoublant", "redoublante"}
        status = get_value(row, "statut", "situation") or "Inscrit"
        student = Student(user_id=user.id, matricule=matricule, first_name=first_name,
                          last_name=last_name, sex=sex, dob=dob,
                          birth_place=get_value(row, "lieu de naissance", "adresse", "lieu naissance"),
                          class_id=school_class.id, status=status, is_repeater=is_repeater)
        db.session.add(student)
        if photo_files:
            match = photo_files.get(_photo_key(matricule)) or photo_files.get(_photo_key(full_name))
            if match:
                filename, image_bytes = match
                photo = save_student_photo(FileStorage(stream=BytesIO(image_bytes), filename=filename), matricule)
                if photo:
                    student.photo = photo
        created += 1

    db.session.commit()
    _store_report("élèves", created, skipped, errors)
    flash(f"{created} élève(s) importé(s). {skipped} ligne(s) ignorée(s).", "success" if created else "warning")
    if errors:
        flash("Consultez le rapport d’import pour corriger les lignes ignorées.", "warning")
    return redirect(url_for("students_list"))


@app.route("/eleves/import/previsualiser", methods=["POST"])
@roles_required("directeur")
def students_import_preview():
    file = request.files.get("import_file")
    if not file or not file.filename:
        flash("Sélectionnez d’abord le fichier Excel ou CSV des élèves.", "warning")
        return redirect(url_for("student_enroll"))
    try:
        rows = read_tabular_rows(file)
    except ValueError as exc:
        flash(f"Prévisualisation impossible : {exc}.", "danger")
        return redirect(url_for("student_enroll"))
    chosen_class_id = request.form.get("class_id", type=int)
    chosen_department_id = request.form.get("department_id", type=int)
    chosen_class = SchoolClass.query.get(chosen_class_id) if chosen_class_id else None
    if chosen_class_id and not chosen_class:
        flash("La classe cible sélectionnée est introuvable.", "danger")
        return redirect(url_for("student_enroll"))
    if chosen_class and chosen_department_id and chosen_class.department_id != chosen_department_id:
        flash("La classe cible ne relève pas de la filière sélectionnée.", "danger")
        return redirect(url_for("student_enroll"))
    import_id = uuid.uuid4().hex
    temp_dir = os.path.join(tempfile.gettempdir(), "ltt-student-imports")
    os.makedirs(temp_dir, exist_ok=True)
    source_path = os.path.join(temp_dir, f"{import_id}-{os.path.basename(file.filename)}")
    file.stream.seek(0)
    file.save(source_path)
    archive_path = None
    archive = request.files.get("photos_zip")
    if archive and archive.filename:
        if not archive.filename.lower().endswith(".zip"):
            os.remove(source_path)
            flash("Les photos doivent être envoyées dans une archive ZIP.", "danger")
            return redirect(url_for("student_enroll"))
        archive_path = os.path.join(temp_dir, f"{import_id}-photos.zip")
        archive.save(archive_path)
    try:
        photos = _read_photo_archive(archive_path)
    except (zipfile.BadZipFile, ValueError) as exc:
        if archive_path and os.path.exists(archive_path):
            os.remove(archive_path)
        os.remove(source_path)
        flash(f"Archive de photos invalide : {exc}.", "danger")
        return redirect(url_for("student_enroll"))
    preview, errors = _preview_student_rows(
        rows,
        chosen_class,
        classes_by_identifier=_class_lookup(),
        department_id=chosen_department_id,
    )
    for row in preview:
        row["photo_found"] = bool(photos.get(_photo_key(row["matricule"])) or photos.get(_photo_key(row["full_name"])))
    session["pending_student_import"] = {"id": import_id, "source_path": source_path, "archive_path": archive_path,
                                        "class_id": chosen_class_id, "department_id": chosen_department_id}
    return render_template(
        "students_import_preview.html",
        preview=preview,
        errors=errors,
        total_rows=len(rows),
        selected_class=chosen_class,
        photo_count=len(photos),
        valid_rows=len(preview),
    )


@app.route("/eleves/import/confirmer", methods=["POST"])
@roles_required("directeur")
def students_import_confirm():
    pending = session.pop("pending_student_import", None)
    if not pending or not os.path.exists(pending["source_path"]):
        flash("La prévisualisation a expiré. Recommencez l’import.", "warning")
        return redirect(url_for("student_enroll"))
    try:
        with open(pending["source_path"], "rb") as source:
            rows = read_tabular_rows(FileStorage(stream=source, filename=os.path.basename(pending["source_path"])))
        photos = _read_photo_archive(pending.get("archive_path"))
        return students_import_v2(rows=rows, photo_files=photos,
                                  chosen_class_id=pending.get("class_id"),
                                  chosen_department_id=pending.get("department_id"))
    except (ValueError, zipfile.BadZipFile) as exc:
        flash(f"Import impossible : {exc}.", "danger")
        return redirect(url_for("student_enroll"))
    finally:
        for path in (pending.get("source_path"), pending.get("archive_path")):
            if path and os.path.exists(path):
                os.remove(path)


# Les deux routes historiques conservent leurs URL et leurs formulaires ; seules leurs
# fonctions sont remplacées après l’enregistrement du module directeur.
app.view_functions["teachers_import"] = roles_required("directeur")(teachers_import_v2)
app.view_functions["students_import"] = roles_required("directeur")(students_import_v2)
