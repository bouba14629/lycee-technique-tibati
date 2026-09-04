from functools import wraps
from datetime import datetime, date, timedelta
import secrets
from flask import session, redirect, url_for, flash, abort
from models import db, Grade, Course, Student, ScheduleEntry, Notification, BulletinWorkAppreciation

DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
TERMS = ["Trimestre 1", "Trimestre 2", "Trimestre 3"]
TERM_ORDINALS = {"Trimestre 1": "PREMIER", "Trimestre 2": "DEUXIÈME", "Trimestre 3": "TROISIÈME"}
TERM_SEQUENCES = {"Trimestre 1": (1, 2), "Trimestre 2": (3, 4), "Trimestre 3": (5, 6)}

ROLE_PASSWORD_CODES = {
    "directeur": "DIR", "censeur": "CEN", "censeur_crm": "CRM",
    "surveillant_general": "SVG", "conseiller_orientation": "COP",
    "chef_travaux": "CDT", "chef_crm": "CCR", "enseignant": "ENS",
    "parent": "PAR", "eleve": "ELV",
}


def generate_account_password(full_name, role):
    """Construit un mot de passe non prédictible, identifiable par rôle et sûr à remettre une seule fois."""
    initials = "".join(part[0].upper() for part in full_name.split() if part)[:3] or "LTT"
    code = ROLE_PASSWORD_CODES.get(role, "LTT")
    return f"Ltt-{code}-{initials}{secrets.token_urlsafe(7)}!"
# Grille horaire officielle du LTT (9 créneaux/jour, avec récréations après le créneau 3 et la pause déjeuner après le 6)
OFFICIAL_PERIODS = [
    ("07:30", "08:20"), ("08:20", "09:10"), ("09:10", "10:00"),
    ("10:15", "11:05"), ("11:05", "11:55"), ("11:55", "12:45"),
    ("13:30", "14:20"), ("14:20", "15:10"), ("15:10", "16:00"),
]


def get_current_school_year():
    """Année scolaire actuelle, paramétrable par le Proviseur (page /directeur/parametres) —
    à utiliser partout où l'année scolaire doit s'afficher, plutôt qu'une valeur codée en dur."""
    from models import AppSetting
    setting = AppSetting.query.first()
    if not setting:
        setting = AppSetting(current_school_year="2025-2026")
        db.session.add(setting)
        db.session.commit()
    return setting.current_school_year


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login", next=1))
        return f(*a, **kw)
    return wrapper


def roles_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                abort(403)
            return f(*a, **kw)
        return wrapper
    return deco


def notify(user_id, text, link=None):
    db.session.add(Notification(user_id=user_id, text=text, link=link))


def student_average(student_id, course_id=None, term=None):
    q = Grade.query.filter_by(student_id=student_id)
    if course_id:
        q = q.filter_by(course_id=course_id)
    if term:
        q = q.filter_by(term=term)
    grades = q.all()
    if not grades:
        return None
    total = sum(g.value / g.max_value * 20 for g in grades)
    return round(total / len(grades), 2)


def subject_averages(student_id, term=None):
    """Retourne liste (course, moyenne, coefficient) pour un élève."""
    student = Student.query.get(student_id)
    if not student or not student.class_id:
        return []
    courses = Course.query.filter_by(class_id=student.class_id).all()
    result = []
    for c in courses:
        avg = student_average(student_id, course_id=c.id, term=term)
        if avg is not None:
            result.append({"course": c, "average": avg, "coef": c.subject.coefficient})
    return result


def general_average(student_id, term=None):
    rows = subject_averages(student_id, term=term)
    if not rows:
        return None
    tot_points = sum(r["average"] * r["coef"] for r in rows)
    tot_coef = sum(r["coef"] for r in rows)
    return round(tot_points / tot_coef, 2) if tot_coef else None


def _notes_trim(student_id, course_id, term):
    """Note trimestrielle (continue) : calculée AUTOMATIQUEMENT comme la moyenne de toutes les petites
    notes de devoir/interrogation saisies par l'enseignant au fil du trimestre — l'enseignant ne saisit
    jamais directement une "note trimestrielle", il ajoute des notes de contrôle continu et le système
    en fait la moyenne lui-même."""
    grades = Grade.query.filter_by(student_id=student_id, course_id=course_id, term=term, type="Devoir").all()
    if not grades:
        return None
    vals = [g.value / g.max_value * 20 for g in grades]
    return round(sum(vals) / len(vals), 2)


def _sequence_value(student_id, course_id, term, which):
    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
    seq_num = seq_a if which == "a" else seq_b
    g = (Grade.query.filter_by(student_id=student_id, course_id=course_id, term=term,
                                type="Évaluation", sequence=seq_num)
         .order_by(Grade.date.desc()).first())
    if not g:
        return None
    return round(g.value / g.max_value * 20, 2)


def course_average(student_id, course_id, term):
    """Moyenne officielle d'une matière : moyenne de (Notes Trim., Éval.3, Éval.4)."""
    nt = _notes_trim(student_id, course_id, term)
    ea = _sequence_value(student_id, course_id, term, "a")
    eb = _sequence_value(student_id, course_id, term, "b")
    vals = [v for v in (nt, ea, eb) if v is not None]
    if not vals:
        return None, nt, ea, eb
    return round(sum(vals) / len(vals), 2), nt, ea, eb


def _notes_trim_display(nt, ea, eb):
    """Valeur affichée dans la colonne 'Notes Trim.' du bulletin : la vraie moyenne des notes continues
    si l'enseignant en a saisi, sinon la moyenne des évaluations disponibles (Éval.1/Éval.2) — cette
    substitution ne change JAMAIS la moyenne générale de la matière (mathématiquement identique dans ce
    cas précis), elle évite seulement d'afficher un tiret trompeur quand l'enseignant n'a saisi que les
    deux évaluations, sans jamais utiliser le contrôle continu séparé."""
    if nt is not None:
        return nt
    vals = [v for v in (ea, eb) if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def appreciation_code(avg):
    if avg is None:
        return ""
    if avg >= 16:
        return "Compétences très bien acquises (A)"
    if avg >= 14:
        return "Compétences bien acquises (B+)"
    if avg >= 12:
        return "Compétences bien acquises (B)"
    if avg >= 10:
        return "Compétences moyennement acquises (C)"
    return "Compétences non acquises (D)"


def automatic_work_appreciation(categories):
    """Produit l’appréciation de travail selon les moyennes d’enseignement disponibles."""
    teaching_averages = [category.get("moyenne") for category in categories if category.get("moyenne") is not None]
    if not teaching_averages:
        return ""
    if all(average < 10 for average in teaching_averages):
        return "Un effort s’impose en tout."
    if any(average < 10 for average in teaching_averages):
        return "Un effort s’impose en cet enseignement."
    return ""


def bulletin_data(student, term=None):
    """Calcule toutes les données du bulletin officiel : matières groupées par catégorie,
    totaux, rang par matière et général, profil de classe, discipline et mentions."""
    from models import Subject, SUBJECT_CATEGORIES, Sanction, Attendance
    term = term or TERMS[0]
    if not student.class_id:
        return None
    courses = Course.query.filter_by(class_id=student.class_id).all()
    classmates = student.school_class.students

    # moyenne + rang par matière, groupés par catégorie
    categories = []
    overall_points, overall_coef = 0.0, 0
    for cat in SUBJECT_CATEGORIES:
        cat_courses = [c for c in courses if c.subject.category == cat]
        if not cat_courses:
            continue
        rows = []
        cat_points, cat_coef, pending_count = 0.0, 0, 0
        for c in cat_courses:
            avg, nt, ea, eb = course_average(student.id, c.id, term)
            coef = c.subject.coefficient
            if avg is None:
                rows.append({"course": c, "notes_trim": None, "eval_a": ea, "eval_b": eb, "coef": coef,
                             "points": None, "average": None, "rank": None, "class_size": 0,
                             "pending": True, "appreciation": "Notes en attente"})
                pending_count += 1
                continue
            points = round(avg * coef, 2)
            # rang de l'élève dans la classe pour cette matière
            peer_avgs = []
            for peer in classmates:
                pavg, _, _, _ = course_average(peer.id, c.id, term)
                if pavg is not None:
                    peer_avgs.append((peer.id, pavg))
            peer_avgs.sort(key=lambda x: -x[1])
            rank = next((i + 1 for i, (pid, _) in enumerate(peer_avgs) if pid == student.id), None)
            rows.append({"course": c, "notes_trim": _notes_trim_display(nt, ea, eb), "eval_a": ea, "eval_b": eb, "coef": coef,
                          "points": points, "average": avg, "rank": rank, "class_size": len(peer_avgs),
                          "pending": False, "appreciation": appreciation_code(avg)})
            cat_points += points
            cat_coef += coef
        if rows:
            categories.append({"name": cat, "rows": rows, "total_points": round(cat_points, 2),
                                "total_coef": cat_coef,
                                "pending_count": pending_count,
                                "moyenne": round(cat_points / cat_coef, 2) if cat_coef else None})
            overall_points += cat_points
            overall_coef += cat_coef

    overall_avg = round(overall_points / overall_coef, 2) if overall_coef else None

    # profil de la classe : moyennes de tous les élèves de la classe
    class_avgs = []
    class_eval_a_vals, class_eval_b_vals = [], []
    for peer in classmates:
        p_points, p_coef = 0.0, 0
        pa_points, pa_coef = 0.0, 0
        pb_points, pb_coef = 0.0, 0
        for c in courses:
            pavg, p_nt, p_ea, p_eb = course_average(peer.id, c.id, term)
            if pavg is not None:
                p_points += pavg * c.subject.coefficient
                p_coef += c.subject.coefficient
            if p_ea is not None:
                pa_points += p_ea * c.subject.coefficient
                pa_coef += c.subject.coefficient
            if p_eb is not None:
                pb_points += p_eb * c.subject.coefficient
                pb_coef += c.subject.coefficient
        if p_coef:
            class_avgs.append((peer.id, round(p_points / p_coef, 2)))
        if pa_coef:
            class_eval_a_vals.append(pa_points / pa_coef)
        if pb_coef:
            class_eval_b_vals.append(pb_points / pb_coef)
    class_avgs.sort(key=lambda x: -x[1])
    rank = next((i + 1 for i, (pid, _) in enumerate(class_avgs) if pid == student.id), None)
    class_size = len(class_avgs)
    class_avg = round(sum(a for _, a in class_avgs) / class_size, 2) if class_size else None
    highest_avg = class_avgs[0][1] if class_avgs else None
    lowest_avg = class_avgs[-1][1] if class_avgs else None
    nb_above_10 = sum(1 for _, a in class_avgs if a >= 10)
    success_rate = round(nb_above_10 / class_size * 100, 1) if class_size else None
    class_eval_a_avg = round(sum(class_eval_a_vals) / len(class_eval_a_vals), 2) if class_eval_a_vals else None
    class_eval_b_avg = round(sum(class_eval_b_vals) / len(class_eval_b_vals), 2) if class_eval_b_vals else None

    # discipline
    absences = Attendance.query.filter_by(student_id=student.id, type="Absence").all()
    retards = Attendance.query.filter_by(student_id=student.id, type="Retard").count()
    just_days = sum(1 for a in absences if a.justified)
    non_just_days = sum(1 for a in absences if not a.justified)

    def _hours(records):
        total = 0.0
        for a in records:
            try:
                h1, m1 = map(int, a.start_time.split(":"))
                h2, m2 = map(int, a.end_time.split(":"))
                total += max(0, (h2 * 60 + m2 - h1 * 60 - m1) / 60)
            except Exception:
                pass
        return round(total, 1)

    just_hours = _hours([a for a in absences if a.justified])
    non_just_hours = _hours([a for a in absences if not a.justified])

    sanctions = Sanction.query.filter_by(student_id=student.id).all()
    avert_conduite = any("avert" in s.type.lower() for s in sanctions)
    blame_conduite = any("blâme" in s.type.lower() or "blame" in s.type.lower() for s in sanctions)
    exclusions = [s for s in sanctions if "exclusion" in s.type.lower()]

    # mentions "travail de l'élève" (dérivées de la moyenne générale)
    work_marks = {k: False for k in [
        "tableau_honneur", "felicitations", "encouragements", "assez_bon_travail",
        "bon_travail", "travail_passable", "travail_insuffisant"]}
    if overall_avg is not None:
        if overall_avg >= 16:
            work_marks["tableau_honneur"] = True
            work_marks["felicitations"] = True
        elif overall_avg >= 14:
            work_marks["encouragements"] = True
        elif overall_avg >= 12:
            work_marks["assez_bon_travail"] = True
        elif overall_avg >= 10:
            work_marks["bon_travail"] = True
        elif overall_avg >= 8:
            work_marks["travail_passable"] = True
        else:
            work_marks["travail_insuffisant"] = True

    saved_appreciation = BulletinWorkAppreciation.query.filter_by(student_id=student.id, term=term).first()
    automatic_appreciation = automatic_work_appreciation(categories)
    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
    return {
        "term": term, "term_seq_a": seq_a, "term_seq_b": seq_b, "categories": categories,
        "overall_points": round(overall_points, 2),
        "overall_coef": overall_coef, "overall_avg": overall_avg, "rank": rank, "class_size": class_size,
        "class_avg": class_avg, "highest_avg": highest_avg, "lowest_avg": lowest_avg,
        "nb_above_10": nb_above_10, "success_rate": success_rate,
        "class_eval_a_avg": class_eval_a_avg, "class_eval_b_avg": class_eval_b_avg,
        "absences_justified_hours": just_hours, "absences_justified_days": just_days,
        "absences_non_justified_hours": non_just_hours, "absences_non_justified_days": non_just_days,
        "retards": retards, "avert_conduite": avert_conduite, "blame_conduite": blame_conduite,
        "exclusions": exclusions, "work_marks": work_marks,
        "automatic_work_appreciation": automatic_appreciation,
        "work_appreciation": saved_appreciation.content if saved_appreciation else automatic_appreciation,
    }


def schedule_group_labels(entries):
    """Retourne les codes de classes à afficher dans un emploi du temps individuel."""
    labels = {}
    grouped = {}
    for entry in entries:
        if entry.group_key:
            grouped.setdefault(entry.group_key, []).append(entry)
        else:
            school_class = entry.course.school_class
            labels[entry.id] = school_class.code or school_class.name
    for grouped_entries in grouped.values():
        classes = [entry.course.school_class for entry in grouped_entries]
        label = " + ".join(sorted({cls.code or cls.name for cls in classes}))
        for entry in grouped_entries:
            labels[entry.id] = label
    return labels


def annual_bulletin_data(student):
    """Calcule le bulletin annuel sur les trois trimestres sans modifier le bulletin trimestriel."""
    from models import SUBJECT_CATEGORIES
    if not student.class_id:
        return None
    terms = TERMS[:3]
    categories, points_total, coef_total = [], 0.0, 0
    term_points, term_coefs = [0.0, 0.0, 0.0], [0, 0, 0]
    for category in SUBJECT_CATEGORIES:
        rows = []
        for course in Course.query.filter_by(class_id=student.class_id).all():
            if course.subject.category != category:
                continue
            term_values = []
            for term in terms:
                values = [g.value / (g.max_value or 20) * 20 for g in Grade.query.filter_by(student_id=student.id, course_id=course.id, term=term).all()]
                term_values.append(round(sum(values) / len(values), 2) if values else None)
            known = [value for value in term_values if value is not None]
            annual = round(sum(known) / len(known), 2) if known else None
            coef = course.subject.coefficient or 1
            points = round(annual * coef, 2) if annual is not None else None
            for index, value in enumerate(term_values):
                if value is not None:
                    term_points[index] += value * coef
                    term_coefs[index] += coef
            rank = None
            if annual is not None:
                peer_annuals = []
                for peer in student.school_class.students:
                    peer_terms = []
                    for term in terms:
                        peer_values = [grade.value / (grade.max_value or 20) * 20 for grade in Grade.query.filter_by(student_id=peer.id, course_id=course.id, term=term).all()]
                        if peer_values:
                            peer_terms.append(sum(peer_values) / len(peer_values))
                    if peer_terms:
                        peer_annuals.append(sum(peer_terms) / len(peer_terms))
                rank = 1 + sum(1 for peer_annual in peer_annuals if peer_annual > annual)
            rows.append({"course": course, "teacher": course.teacher, "terms": term_values, "annual": annual,
                         "coef": coef, "points": points, "rank": rank})
            if points is not None:
                points_total += points
                coef_total += coef
        if rows:
            cat_points = round(sum(row["points"] or 0 for row in rows), 2)
            cat_coef = sum(row["coef"] for row in rows if row["annual"] is not None)
            categories.append({"name": category, "rows": rows, "total_points": cat_points, "total_coef": cat_coef,
                               "average": round(cat_points / cat_coef, 2) if cat_coef else None})
    overall_avg = round(points_total / coef_total, 2) if coef_total else None

    def peer_annual_average(peer):
        peer_points, peer_coefs = 0.0, 0
        for course in Course.query.filter_by(class_id=peer.class_id).all():
            values_by_term = []
            for item_term in terms:
                values = [grade.value / (grade.max_value or 20) * 20 for grade in Grade.query.filter_by(student_id=peer.id, course_id=course.id, term=item_term).all()]
                if values:
                    values_by_term.append(sum(values) / len(values))
            if values_by_term:
                coefficient = course.subject.coefficient or 1
                peer_points += (sum(values_by_term) / len(values_by_term)) * coefficient
                peer_coefs += coefficient
        return round(peer_points / peer_coefs, 2) if peer_coefs else None

    class_averages = [peer_annual_average(peer) for peer in student.school_class.students]
    class_averages = [value for value in class_averages if value is not None]
    class_rank = 1 + sum(1 for value in class_averages if overall_avg is not None and value > overall_avg)
    return {"terms": terms, "categories": categories, "overall_points": round(points_total, 2),
            "overall_coef": coef_total, "overall_avg": overall_avg,
            "term_averages": [round(term_points[index] / term_coefs[index], 2) if term_coefs[index] else None for index in range(3)],
            "class_size": len(student.school_class.students),
            "class_avg": round(sum(class_averages) / len(class_averages), 2) if class_averages else None,
            "class_high": max(class_averages) if class_averages else None,
            "class_low": min(class_averages) if class_averages else None,
            "rank": class_rank if overall_avg is not None else None}


def build_official_grid(entries, days=None):
    """Projette une liste de créneaux sur la grille officielle à 9 périodes.

    Les anciens créneaux pouvaient couvrir plusieurs périodes (par exemple 07:30–09:30).
    On les affiche dans chaque colonne qu'ils recouvrent, plutôt que de les ignorer faute
    de correspondance exacte avec un horaire officiel.
    """
    days = days or DAYS[:5]
    grid = {d: [None] * len(OFFICIAL_PERIODS) for d in days}
    labels = schedule_group_labels(entries)
    for e in entries:
        e.display_class_label = labels.get(e.id, e.course.school_class.code or e.course.school_class.name)
        if e.day not in grid:
            continue
        for i, (start, end) in enumerate(OFFICIAL_PERIODS):
            if e.start_time < end and start < e.end_time:
                grid[e.day][i] = e
    return grid


def filled_official_slots(grid):
    """Compte les cellules non vides réellement affichées dans une grille officielle."""
    return sum(1 for day_slots in grid.values() for entry in day_slots if entry is not None)


def check_schedule_conflict(day, start, end, room_id=None, teacher_id=None, class_id=None, exclude_id=None, group_key=None):
    """Renvoie une liste de messages de conflit (salle/enseignant/classe) pour un créneau donné.
    group_key : si fourni, les créneaux partageant le même group_key (cours en tronc commun réunissant
    plusieurs classes) ne sont jamais considérés comme en conflit de salle/enseignant entre eux."""
    conflicts = []
    q = ScheduleEntry.query.filter(ScheduleEntry.day == day)
    if exclude_id:
        q = q.filter(ScheduleEntry.id != exclude_id)
    entries = q.all()

    def overlap(s1, e1, s2, e2):
        return s1 < e2 and s2 < e1

    for e in entries:
        if not overlap(start, end, e.start_time, e.end_time):
            continue
        if group_key and e.group_key == group_key:
            continue  # même groupe de tronc commun : le partage de salle/enseignant est volontaire
        if room_id and e.room_id == room_id:
            conflicts.append(f"Salle déjà occupée le {day} de {e.start_time} à {e.end_time}")
        if teacher_id and e.course.teacher_id == teacher_id:
            conflicts.append(f"Enseignant déjà en cours le {day} de {e.start_time} à {e.end_time}")
        if class_id and e.course.class_id == class_id:
            conflicts.append(f"Classe déjà en cours le {day} de {e.start_time} à {e.end_time}")
    return conflicts


def parse_date(s, default=None):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return default


def section_department_ids(section_id):
    """Liste des id de départements appartenant à une section donnée."""
    from models import Department
    return [d.id for d in Department.query.filter_by(section_id=section_id).all()]


def user_scoped_department_ids(user):
    """Départements accessibles à un compte scopé par section (Censeur/Surveillant Général/Chef des Travaux).
    Renvoie None si le compte n'est pas limité à une section (portée transversale, ex. Censeur Enseignements Généraux)."""
    if user.role in ("censeur", "surveillant_general", "chef_travaux") and user.section_id:
        return section_department_ids(user.section_id)
    return None


def user_scoped_class_ids(user):
    """Classes accessibles à un compte scopé par section. None = pas de restriction."""
    from models import SchoolClass
    dept_ids = user_scoped_department_ids(user)
    if dept_ids is None:
        return None
    return [c.id for c in SchoolClass.query.filter(SchoolClass.department_id.in_(dept_ids)).all()]


def dashboard_rates(class_ids=None):
    """Indicateurs globaux (taux) pour les jauges du tableau de bord, éventuellement limités
    à une liste de classes (portée d'un Censeur/Surveillant Général)."""
    from models import Grade, Student, Attendance, Teacher, Course

    student_q = Student.query
    if class_ids is not None:
        student_q = student_q.filter(Student.class_id.in_(class_ids))
    student_ids = [s.id for s in student_q.all()]
    total_students = len(student_ids) or 1

    grade_q = Grade.query
    if class_ids is not None:
        grade_q = grade_q.filter(Grade.student_id.in_(student_ids))
    grades = grade_q.all()
    if grades:
        passing = sum(1 for g in grades if g.max_value and (g.value / g.max_value * 20) >= 10)
        success_rate = round(passing / len(grades) * 100)
    else:
        success_rate = 0

    att_q = Attendance.query
    if class_ids is not None:
        att_q = att_q.filter(Attendance.student_id.in_(student_ids))
    absence_students = {a.student_id for a in att_q.filter_by(type="Absence").all()}
    retard_students = {a.student_id for a in att_q.filter_by(type="Retard").all()}
    absence_rate = round(len(absence_students) / total_students * 100)
    retard_rate = round(len(retard_students) / total_students * 100)

    teacher_q = Teacher.query
    if class_ids is not None:
        teacher_q = teacher_q.join(Course).filter(Course.class_id.in_(class_ids)).distinct()
    teachers = teacher_q.all()
    active_rate = round(sum(1 for t in teachers if t.user.active) / (len(teachers) or 1) * 100)

    return {
        "success_rate": success_rate,
        "absence_rate": absence_rate,
        "retard_rate": retard_rate,
        "active_rate": active_rate,
    }


def department_success_rates(dept_ids=None):
    """% d'élèves avec moyenne >= 10 (simple, toutes notes confondues), par filière — pour le graphique."""
    from models import Department, Grade

    q = Department.query
    if dept_ids is not None:
        q = q.filter(Department.id.in_(dept_ids))
    depts = q.order_by(Department.code).all()
    results = []
    for d in depts:
        student_ids = [s.id for c in d.classes for s in c.students]
        if not student_ids:
            results.append((d.code, 0))
            continue
        rows = (Grade.query.with_entities(Grade.student_id, Grade.value, Grade.max_value)
                .filter(Grade.student_id.in_(student_ids)).all())
        per_student = {}
        for sid, val, maxval in rows:
            per_student.setdefault(sid, []).append(val / maxval * 20 if maxval else 0)
        if not per_student:
            results.append((d.code, 0))
            continue
        passing = sum(1 for vals in per_student.values() if sum(vals) / len(vals) >= 10)
        results.append((d.code, round(passing / len(per_student) * 100)))
    return results


def evolution_series(class_ids=None, term=None):
    """Moyenne (Notes Trim. / Éval.A / Éval.B / Générale) sur le périmètre donné — pour le graphique d'évolution."""
    from models import Grade, Student
    term = term or TERMS[0]
    student_q = Student.query
    if class_ids is not None:
        student_q = student_q.filter(Student.class_id.in_(class_ids))
    student_ids = [s.id for s in student_q.all()]
    if not student_ids:
        return {"labels": ["Continu", "Éval.1", "Éval.2", "Générale"], "values": [0, 0, 0, 0]}

    def avg_for(gtype, seq=None):
        q = Grade.query.filter(Grade.student_id.in_(student_ids), Grade.term == term, Grade.type == gtype)
        if seq is not None:
            q = q.filter(Grade.sequence == seq)
        vals = [(g.value / g.max_value * 20 if g.max_value else 0) for g in q.all()]
        return round(sum(vals) / len(vals), 1) if vals else 0

    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
    v_trim = avg_for("Devoir")
    v_a = avg_for("Évaluation", seq_a)
    v_b = avg_for("Évaluation", seq_b)
    present = [v for v in (v_trim, v_a, v_b) if v]
    v_general = round(sum(present) / len(present), 1) if present else 0
    return {"labels": ["Continu", f"Éval.{seq_a}", f"Éval.{seq_b}", "Générale"],
            "values": [v_trim, v_a, v_b, v_general]}


def dashboard_alerts(class_ids=None, department_ids=None):
    """Liste d'alertes contextuelles pour le panneau 'Alertes & Notifications' du tableau de bord."""
    from models import Student, Attendance, Course, PlannedAssessment, ScheduleEntry, SchoolClass, Grade
    alerts = []
    absence_threshold = 3
    absence_window_start = date.today() - timedelta(days=30)

    student_q = Student.query
    if class_ids is not None:
        student_q = student_q.filter(Student.class_id.in_(class_ids))
    student_ids = [s.id for s in student_q.all()]

    if student_ids:
        att_counts = {}
        for a in Attendance.query.filter(Attendance.student_id.in_(student_ids), Attendance.type == "Absence",
                                         Attendance.date >= absence_window_start).all():
            att_counts[a.student_id] = att_counts.get(a.student_id, 0) + 1
        many_absences = sum(1 for c in att_counts.values() if c >= absence_threshold)
        if many_absences:
            alerts.append(("danger", "bi-exclamation-octagon-fill", "Absences",
                            f"{many_absences} élève(s) atteignent {absence_threshold} absences ou plus sur les 30 derniers jours", "censeur_absences"))
        late_threshold = 3
        late_counts = {}
        for attendance in Attendance.query.filter(Attendance.student_id.in_(student_ids), Attendance.type == "Retard",
                                                  Attendance.date >= absence_window_start).all():
            late_counts[attendance.student_id] = late_counts.get(attendance.student_id, 0) + 1
        repeated_late = sum(1 for count in late_counts.values() if count >= late_threshold)
        if repeated_late:
            alerts.append(("warning", "bi-clock-history", "Retards répétés",
                           f"{repeated_late} élève(s) atteignent {late_threshold} retards ou plus sur les 30 derniers jours", "late_arrivals"))

    course_q = Course.query
    class_q = SchoolClass.query
    if department_ids is not None:
        course_q = course_q.join(SchoolClass).filter(SchoolClass.department_id.in_(department_ids))
        class_q = class_q.filter(SchoolClass.department_id.in_(department_ids))
    courses = course_q.all()
    courses_without_grades = sum(1 for c in courses if not Grade.query.filter_by(course_id=c.id).first())
    if courses_without_grades:
        alerts.append(("warning", "bi-journal-x", "Évaluations",
                        f"{courses_without_grades} cours sans aucune note saisie", "censeur_indicators"))

    assessment_q = PlannedAssessment.query.join(Course).join(SchoolClass)
    if class_ids is not None:
        assessment_q = assessment_q.filter(Course.class_id.in_(class_ids))
    elif department_ids is not None:
        assessment_q = assessment_q.filter(SchoolClass.department_id.in_(department_ids))
    overdue_assessments = assessment_q.filter(PlannedAssessment.scheduled_date <= date.today(),
                                               PlannedAssessment.status != "Saisie complète").count()
    if overdue_assessments:
        alerts.append(("danger", "bi-clipboard2-x-fill", "Évaluations à finaliser",
                       f"{overdue_assessments} évaluation(s) arrivée(s) à échéance sans saisie complète", "evaluation_plan"))

    classes_without_edt = 0
    for cls in class_q.all():
        has_entry = ScheduleEntry.query.join(Course).filter(Course.class_id == cls.id).first()
        if not has_entry:
            classes_without_edt += 1
    if classes_without_edt:
        alerts.append(("info", "bi-calendar2-x-fill", "Emplois du temps",
                        f"{classes_without_edt} classe(s) sans emploi du temps", "censeur_schedule"))

    if not alerts:
        alerts.append(("success", "bi-check-circle-fill", "Tout est à jour",
                        "Aucune alerte particulière pour le moment", None))
    return alerts


def recent_activity_feed(class_ids=None, department_ids=None, limit=6):
    """Fil d'activité récente (notes saisies, absences, inscriptions) pour le tableau de bord."""
    from models import Grade, Student, Course, SchoolClass
    events = []

    grade_q = Grade.query.order_by(Grade.date.desc())
    if class_ids is not None:
        grade_q = grade_q.join(Student).filter(Student.class_id.in_(class_ids))
    for g in grade_q.limit(5).all():
        events.append((g.date, "bi-journal-check", f"Note saisie — {g.course.subject.name} / {g.course.school_class.name}"))

    student_q = Student.query.order_by(Student.enrolled_on.desc())
    if class_ids is not None:
        student_q = student_q.filter(Student.class_id.in_(class_ids))
    for s in student_q.limit(5).all():
        events.append((s.enrolled_on.date() if hasattr(s.enrolled_on, "date") else s.enrolled_on,
                        "bi-person-plus-fill", f"Élève inscrit : {s.full_name} ({s.school_class.name if s.school_class else '—'})"))

    events.sort(key=lambda e: e[0] or datetime.min.date(), reverse=True)
    return events[:limit]


def equipment_rates(room_ids):
    """Taux liés au parc d'équipements/salles (Chef des Travaux / Chef de Centre CRM)."""
    from models import Room, Equipment, MaintenanceRequest
    rooms = Room.query.filter(Room.id.in_(room_ids)).all() if room_ids else []
    equipments = Equipment.query.filter(Equipment.room_id.in_(room_ids)).all() if room_ids else []
    total_eq = len(equipments) or 1
    operational = sum(1 for e in equipments if e.status == "Opérationnel")
    maint = MaintenanceRequest.query.filter(MaintenanceRequest.room_id.in_(room_ids)).all() if room_ids else []
    resolved = sum(1 for m in maint if m.status == "Résolue")
    total_maint = len(maint) or 1
    return {
        "success_rate": round(operational / total_eq * 100),
        "absence_rate": round((total_eq - operational) / total_eq * 100),
        "retard_rate": round(resolved / total_maint * 100),
        "active_rate": round(len(rooms) and 100 or 0),
    }


def _observation_label(pct):
    """Appréciation du taux de réussite d'une classe — seuils calibrés sur le modèle réel fourni par l'établissement."""
    if pct is None:
        return ""
    if pct < 33.33:
        return "Faible taux de réussite"
    if pct < 60:
        return "Taux de réussite moyen"
    return "Bon taux de réussite"


def _fast_overall_averages(cls, term, subject_category=None, sequence=None, course_id=None, subject_ids=None):
    """Calcule la moyenne générale de chaque élève d'une classe en 1 seule requête groupée
    (même formule officielle que bulletin_data, mais bien plus rapide sur un grand nombre d'élèves —
    nécessaire pour les statistiques de conseil de classe qui portent sur toute la classe/l'établissement).
    Si subject_category est fourni, seules les matières de cette catégorie entrent dans le calcul
    (utilisé par le Censeur Enseignements Généraux, dont la fiche ne doit concerner que ses propres matières)."""
    from models import Course, Grade
    seq_a, seq_b = TERM_SEQUENCES.get(term, (1, 2))
    courses_q = Course.query.filter_by(class_id=cls.id)
    if course_id is not None:
        courses_q = courses_q.filter(Course.id == course_id)
    elif subject_ids:
        courses_q = courses_q.filter(Course.subject_id.in_(subject_ids))
    if subject_category:
        courses_q = courses_q.join(Course.subject).filter_by(category=subject_category)
    courses = courses_q.all()
    course_coef = {c.id: c.subject.coefficient for c in courses}
    student_ids = [s.id for s in cls.students]
    if not course_coef or not student_ids:
        return {sid: None for sid in student_ids}

    grades_q = Grade.query.filter(Grade.course_id.in_(list(course_coef.keys())), Grade.term == term,
                                  Grade.student_id.in_(student_ids))
    if sequence is not None:
        grades_q = grades_q.filter(Grade.type == "Évaluation", Grade.sequence == sequence)
    grades = grades_q.all()
    # Évaluations A/B : une seule valeur (la plus récente, upsert) — Notes Trim : moyenne de TOUTES les notes "Devoir"
    latest_eval = {}
    devoir_vals = {}
    for g in grades:
        if g.type == "Devoir":
            devoir_vals.setdefault((g.student_id, g.course_id), []).append(g.value / g.max_value * 20)
        else:
            key = (g.student_id, g.course_id, g.type, g.sequence)
            prev = latest_eval.get(key)
            if prev is None or (g.date or date.min) >= (prev.date or date.min):
                latest_eval[key] = g

    result = {}
    for sid in student_ids:
        points, coef_sum = 0.0, 0
        for cid, coef in course_coef.items():
            vals = []
            if sequence is None:
                dv = devoir_vals.get((sid, cid))
                if dv:
                    vals.append(sum(dv) / len(dv))
                for g in (latest_eval.get((sid, cid, "Évaluation", seq_a)),
                          latest_eval.get((sid, cid, "Évaluation", seq_b))):
                    if g:
                        vals.append(g.value / g.max_value * 20)
            else:
                g = latest_eval.get((sid, cid, "Évaluation", sequence))
                if g:
                    vals.append(g.value / g.max_value * 20)
            if vals:
                points += (sum(vals) / len(vals)) * coef
                coef_sum += coef
        result[sid] = round(points / coef_sum, 2) if coef_sum else None
    return result


def class_statistics(cls, term, subject_category=None, sequence=None, course_id=None, subject_ids=None):
    """Fiche statistique d'une classe pour le conseil de classe (inspirée du modèle officiel fourni) :
    effectifs, moyennes, taux de réussite, mentions — ventilés par sexe (F/G) et total (T)."""
    def split(students, key):
        f = [s for s in students if s.sex == "F"]
        g = [s for s in students if s.sex == "M"]
        return {"F": key(f), "G": key(g), "T": key(students)}

    students = cls.students
    inscrits = split(students, len)

    avg_by_id = _fast_overall_averages(cls, term, subject_category=subject_category,
                                       sequence=sequence, course_id=course_id, subject_ids=subject_ids)

    def mark(avg, name):
        if avg is None:
            return False
        if name == "tableau_honneur" or name == "felicitations":
            return avg >= 16
        if name == "encouragements":
            return avg >= 14
        return False

    evalues_students = [s for s in students if avg_by_id[s.id] is not None]
    evalues = split(evalues_students, len)
    reussite_students = [s for s in evalues_students if avg_by_id[s.id] >= 10]
    reussite = split(reussite_students, len)

    def pct_reussite(sex_students, sex_evalues):
        return round(len(sex_students) / len(sex_evalues) * 100, 2) if sex_evalues else None

    pct = {
        "F": pct_reussite([s for s in reussite_students if s.sex == "F"], [s for s in evalues_students if s.sex == "F"]),
        "G": pct_reussite([s for s in reussite_students if s.sex == "M"], [s for s in evalues_students if s.sex == "M"]),
        "T": pct_reussite(reussite_students, evalues_students),
    }

    th_students = [s for s in evalues_students if mark(avg_by_id[s.id], "tableau_honneur")]
    enc_students = [s for s in evalues_students if mark(avg_by_id[s.id], "encouragements")]
    fel_students = [s for s in evalues_students if mark(avg_by_id[s.id], "felicitations")]
    th = split(th_students, len)
    enc = split(enc_students, len)
    fel = split(fel_students, len)

    avgs = [avg_by_id[s.id] for s in evalues_students]
    moyenne_generale = round(sum(avgs) / len(avgs), 2) if avgs else None

    def extreme(sex, pick_max):
        vals = [avg_by_id[s.id] for s in evalues_students if s.sex == sex]
        if not vals:
            return None
        return round(max(vals) if pick_max else min(vals), 2)

    forte_moyenne = {"F": extreme("F", True), "G": extreme("M", True)}
    faible_moyenne = {"F": extreme("F", False), "G": extreme("M", False)}

    return {
        "class": cls, "inscrits": inscrits, "evalues": evalues, "reussite": reussite, "pct": pct,
        "th": th, "encouragement": enc, "felicitations": fel,
        "moyenne_generale": moyenne_generale, "forte_moyenne": forte_moyenne, "faible_moyenne": faible_moyenne,
        "observation": _observation_label(pct["T"]), "_avgs_by_id": avg_by_id,
    }


LEVEL_ORDER = ["1A", "2A", "3A", "4A", "2nde", "P", "Tle"]


def sort_classes_by_level(classes):
    """Trie une liste de classes par niveau (toutes les 1A ensemble, puis les 2A, etc.),
    puis par nom de filière au sein d'un même niveau."""
    def key(c):
        idx = LEVEL_ORDER.index(c.level) if c.level in LEVEL_ORDER else len(LEVEL_ORDER)
        return (idx, c.department.name if c.department else "")
    return sorted(classes, key=key)


def is_second_cycle(level):
    return level in ("2nde", "P", "Tle")


def council_statistics(classes, term, subject_category=None, sequence=None, course_id=None, subject_ids=None):
    """Regroupe class_statistics() sur un ensemble de classes, avec sous-totaux par cycle et total général —
    reproduit la structure du modèle officiel (FICHE STATISTIQUE DES RESULTATS DU TRIMESTRE)."""
    rows = [class_statistics(c, term, subject_category=subject_category, sequence=sequence,
                             course_id=course_id, subject_ids=subject_ids) for c in classes]
    cycle1 = [r for r in rows if not is_second_cycle(r["class"].level)]
    cycle2 = [r for r in rows if is_second_cycle(r["class"].level)]

    def aggregate(group):
        def sum_key(key1, key2):
            return {sx: sum(r[key1][sx] for r in group) for sx in ("F", "G", "T")}
        inscrits = sum_key("inscrits", None)
        evalues = sum_key("evalues", None)
        reussite = sum_key("reussite", None)
        th = sum_key("th", None)
        enc = sum_key("encouragement", None)
        fel = sum_key("felicitations", None)
        pct = {sx: (round(reussite[sx] / evalues[sx] * 100, 2) if evalues[sx] else None) for sx in ("F", "G", "T")}
        all_avgs = []
        for r in group:
            all_avgs.extend(v for v in r["_avgs_by_id"].values() if v is not None)
        moyenne_generale = round(sum(all_avgs) / len(all_avgs), 2) if all_avgs else None
        forte = {"F": max([r["forte_moyenne"]["F"] for r in group if r["forte_moyenne"]["F"] is not None], default=None),
                 "G": max([r["forte_moyenne"]["G"] for r in group if r["forte_moyenne"]["G"] is not None], default=None)}
        faible = {"F": min([r["faible_moyenne"]["F"] for r in group if r["faible_moyenne"]["F"] is not None], default=None),
                  "G": min([r["faible_moyenne"]["G"] for r in group if r["faible_moyenne"]["G"] is not None], default=None)}
        return {"inscrits": inscrits, "evalues": evalues, "reussite": reussite, "pct": pct,
                "th": th, "encouragement": enc, "felicitations": fel, "moyenne_generale": moyenne_generale,
                "forte_moyenne": forte, "faible_moyenne": faible, "observation": _observation_label(pct["T"])}

    return {
        "rows": rows, "cycle1": cycle1, "cycle2": cycle2,
        "total_cycle1": aggregate(cycle1) if cycle1 else None,
        "total_cycle2": aggregate(cycle2) if cycle2 else None,
        "total_general": aggregate(rows) if rows else None,
    }
