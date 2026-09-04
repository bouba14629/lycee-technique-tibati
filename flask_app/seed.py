"""Peuple la base de données avec la structure du LTT + comptes de démonstration."""
import random
import os
from datetime import date, timedelta
from models import (
    db, User, Section, Department, SchoolClass, Subject, Teacher, Parent, Student,
    Course, Grade, Attendance, Sanction, Reward, Room, Equipment, Reservation,
    ScheduleEntry, Announcement, Message, MaintenanceRequest, Availability, ActivityLog, SchoolCalendarEvent,
)

SECTIONS = {
    "STT": {
        "label": "Sciences et Technologies du Tertiaire",
        "departments": {
            "ACA": "Action et Communication Administratives",
            "ESF": "Économie Sociale et Familiale",
            "CG": "Comptabilité et Gestion",
        },
    },
    "IND": {
        "label": "Industrielle",
        "departments": {
            "GEL": "Génie Électrique",
            "IH": "Industrie de l'Habillement",
            "AMEB": "Ameublement-Ébénisterie",
            "GC": "Génie Civil",
        },
    },
}
# L'Enseignement Général n'est pas une section : ce sont des matières communes (Français, Maths, EPS…)
# dispensées dans toutes les filières des deux sections STT et Industrielle (déjà via GENERAL_SUBJECTS).

# Code de spécialité réellement utilisé par l'établissement pour chaque classe — peut différer du code de
# la filière selon le niveau (ex. Génie Électrique : "ELEQ" au 1er cycle, "F3" au second cycle). Une filière
# absente de cette table (ex. ESF) garde simplement son propre code de département à tous les niveaux.
CLASS_SPECIALTY_MAP = {
    "GEL": {"1A": "ELEQ", "2A": "ELEQ", "3A": "ELEQ", "4A": "ELEQ", "2nde": "F3", "P": "F3", "Tle": "F3"},
    "AMEB": {"1A": "MACO/MENU", "2A": "MENU", "3A": "MENU", "4A": "MENU", "2nde": "AMEB", "P": "AMEB", "Tle": "AMEB"},
    "GC": {"1A": "MACO/MENU", "2A": "MACO", "3A": "MACO", "4A": "MACO", "2nde": "F4/BA", "P": "F4/BA", "Tle": "F4/BA"},
    "IH": {"1A": "COME", "2A": "COME", "3A": "COME", "4A": "COME", "2nde": "IH", "P": "IH", "Tle": "IH"},
    "ACA": {"1A": "STT", "2A": "SECRETARIAT", "3A": "SEBU", "4A": "SEBU", "2nde": "STT", "P": "ACA", "Tle": "ACA"},
    "CG": {"1A": "STT", "2A": "GESTION", "3A": "ESCOM", "4A": "ESCOM", "2nde": "STT", "P": "CG", "Tle": "CG"},
}

GENERAL_SUBJECTS = [
    ("Histoire/Géographie", 2, "Enseignements Généraux"), ("Français", 3, "Enseignements Généraux"),
    ("Anglais", 2, "Enseignements Généraux"), ("ECM", 1, "Enseignements Généraux"),
    ("Informatique", 2, "Enseignements Généraux"), ("Mathématiques", 3, "Enseignements Généraux"),
    ("Sciences Physiques", 2, "Enseignements Généraux"),
    ("EPS", 1, "Enseignements Divers"), ("Travaux Manuels", 1, "Enseignements Divers"),
]
TH = "Enseignements Professionnels Théoriques"
PR = "Enseignements Professionnels Pratiques"
TECH_EXTRA_SUBJECTS = {
    "ACA": [("Communication Administrative", 3, TH), ("Droit", 2, TH), ("Organisation d'Entreprise", 2, TH),
            ("Correspondance Administrative", 2, TH), ("Bureautique (Atelier)", 4, PR), ("Stage Pratique Administratif", 2, PR)],
    "ESF": [("Nutrition", 3, TH), ("Biologie Appliquée", 2, TH), ("Économie Familiale", 2, TH),
            ("Puériculture", 2, TH), ("Travaux Pratiques Cuisine", 4, PR), ("Travaux Pratiques Couture", 3, PR)],
    "CG": [("Comptabilité", 3, TH), ("Fiscalité", 2, TH), ("Droit des Affaires", 2, TH),
           ("Gestion Commerciale", 2, TH), ("Comptabilité Informatisée (Atelier)", 4, PR), ("Stage Pratique Comptable", 2, PR)],
    "GEL": [("Santé et Sécurité", 1, TH), ("Circuits Électriques", 3, TH), ("Technologie des Équipements", 2, TH),
            ("Schémas Électriques", 2, TH), ("Dessin Technique", 2, TH),
            ("Installations Électriques Résidentielles et Commerciales", 5, PR), ("Mesures et Essais Électriques", 3, PR)],
    "IH": [("Technologie de la Couture", 3, TH), ("Patronage et Coupe", 2, TH), ("Textiles et Matières", 2, TH),
           ("Mode et Stylisme", 2, TH), ("Atelier Couture", 5, PR), ("Travaux Pratiques Couture Industrielle", 3, PR)],
    "AMEB": [("Technologie du Bois", 3, TH), ("Dessin Technique du Meuble", 2, TH), ("Structures et Assemblages", 2, TH),
             ("Finition et Sculpture sur Bois", 2, TH), ("Atelier Menuiserie", 5, PR), ("Travaux Pratiques Ébénisterie", 3, PR)],
    "GC": [("Résistance des Matériaux", 3, TH), ("Topographie", 2, TH), ("Dessin du Bâtiment", 2, TH),
           ("Métré et Devis", 2, TH), ("Béton Armé (Atelier)", 5, PR), ("Travaux Pratiques Chantier", 3, PR)],
}
LEVELS = ["1A", "2A", "3A", "4A", "2nde", "P", "Tle"]

FIRST_NAMES_M = ["Jean", "Paul", "Emmanuel", "Samuel", "David", "Aristide", "Boris", "Cédric", "Franck", "Hervé", "Junior", "Landry", "Merlin", "Nathan", "Olivier", "Patrick"]
FIRST_NAMES_F = ["Marie", "Grace", "Chantal", "Estelle", "Florence", "Huguette", "Ines", "Judith", "Laure", "Nadège", "Odile", "Pauline", "Raissa", "Sandrine", "Vanessa", "Yvette"]
LAST_NAMES = ["Mbarga", "Ndjock", "Fouda", "Abena", "Tchoumi", "Mvondo", "Ateba", "Belinga", "Essomba", "Ngo Bassong", "Kamga", "Talla", "Njoya", "Fotso", "Bello", "Douteme", "Amadou", "Bouba"]
BIRTH_PLACES = ["Tibati", "Ngaoundéré", "Ngatt", "Banyo", "Meiganga", "Tignère", "Yoko"]


def rand_name(sex):
    fn = random.choice(FIRST_NAMES_M if sex == "M" else FIRST_NAMES_F)
    ln = random.choice(LAST_NAMES)
    return fn, ln


def slugify(s):
    return s.lower().replace(" ", ".").replace("'", "")


def bootstrap_founder():
    """Crée le seul compte initial d’une instance vierge, sans données ni comptes fictifs."""
    if User.query.first():
        return
    password = os.getenv("LTT_INITIAL_ADMIN_PASSWORD")
    if not password or len(password) < 12:
        raise RuntimeError("LTT_INITIAL_ADMIN_PASSWORD doit contenir au moins 12 caractères.")
    username = os.getenv("LTT_INITIAL_ADMIN_USERNAME", "proviseur").strip().lower() or "proviseur"
    full_name = os.getenv("LTT_INITIAL_ADMIN_NAME", "Proviseur fondateur").strip() or "Proviseur fondateur"
    founder = User(username=username, role="directeur", full_name=full_name,
                   email=os.getenv("LTT_INITIAL_ADMIN_EMAIL", ""), active=True,
                   must_change_password=True)
    founder.set_password(password)
    founder.plain_password = None
    db.session.add(founder)
    db.session.commit()


def seed():
    if User.query.first():
        return  # déjà initialisé

    # --- Sections / Filières / Matières / Classes ---
    section_map = {}
    dept_map = {}
    for scode, sinfo in SECTIONS.items():
        section = Section(name=sinfo["label"], code=scode)
        db.session.add(section)
        db.session.flush()
        section_map[scode] = section
        for dcode, dlabel in sinfo["departments"].items():
            dept = Department(name=dlabel, code=dcode, section_id=section.id, capacity=48)
            db.session.add(dept)
            db.session.flush()
            dept_map[dcode] = dept
            # matières générales pour chaque filière technique + EG lui-même
            subs = list(GENERAL_SUBJECTS)
            if dcode in TECH_EXTRA_SUBJECTS:
                subs += TECH_EXTRA_SUBJECTS[dcode]
            for sname, coef, cat in subs:
                db.session.add(Subject(name=sname, coefficient=coef, category=cat, department_id=dept.id))
            # classes : cycle complet pour chaque filière (2nde à Tle), avec le vrai code de spécialité
            # utilisé par l'établissement pour ce niveau (peut différer du code de département)
            specialty_by_level = CLASS_SPECIALTY_MAP.get(dcode, {})
            for lvl in LEVELS:
                specialty = specialty_by_level.get(lvl, dcode)
                db.session.add(SchoolClass(name=f"{lvl} {specialty}", level=lvl, specialty=specialty,
                                            department_id=dept.id, school_year="2025-2026", capacity=48))
    db.session.flush()

    # --- Proviseurs, Censeurs (1 par section + 1 Enseignements Généraux), Surveillants Généraux (1 par section),
    #     Chefs des Travaux (1 par section), Chef de Centre CRM, Conseiller d'Orientation ---
    directeurs = []
    u = User(username="proviseur1", role="directeur", full_name="Proviseur",
              email="proviseur1@lycee-tibati.cm")
    u.set_password_fast("Direction@2026")
    db.session.add(u)
    directeurs.append(u)

    censeur_stt = User(username="censeur.stt", role="censeur", full_name="Censeur Section STT",
                        email="censeur.stt@lycee-tibati.cm", section_id=section_map["STT"].id)
    censeur_stt.set_password_fast("CenseurSTT@2026")
    db.session.add(censeur_stt)

    censeur_ind = User(username="censeur.ind", role="censeur", full_name="Censeur Section Industrielle",
                        email="censeur.ind@lycee-tibati.cm", section_id=section_map["IND"].id)
    censeur_ind.set_password_fast("CenseurIND@2026")
    db.session.add(censeur_ind)

    censeur_eg = User(username="censeur.eg", role="censeur", full_name="Censeur Enseignements Généraux",
                       email="censeur.eg@lycee-tibati.cm", section_id=None)
    censeur_eg.set_password_fast("CenseurEG@2026")
    db.session.add(censeur_eg)
    censeur = censeur_stt  # compte de référence utilisé plus bas (sanctions/récompenses de démo)

    censeur_crm = User(username="censeur.crm", role="censeur_crm", full_name="Censeur CRM",
                        email="censeur.crm@lycee-tibati.cm", section_id=None)
    censeur_crm.set_password_fast("CenseurCRM@2026")
    db.session.add(censeur_crm)

    surveillant_stt = User(username="surveillant.stt", role="surveillant_general", full_name="Surveillant Général STT",
                            email="surveillant.stt@lycee-tibati.cm", section_id=section_map["STT"].id)
    surveillant_stt.set_password_fast("SurveilSTT@2026")
    db.session.add(surveillant_stt)

    surveillant_ind = User(username="surveillant.ind", role="surveillant_general", full_name="Surveillant Général Industriel",
                            email="surveillant.ind@lycee-tibati.cm", section_id=section_map["IND"].id)
    surveillant_ind.set_password_fast("SurveilIND@2026")
    db.session.add(surveillant_ind)
    surveillant = surveillant_stt  # compte de référence utilisé plus bas

    conseiller = User(username="orientation1", role="conseiller_orientation", full_name="Conseiller d'Orientation",
                       email="orientation1@lycee-tibati.cm")
    conseiller.set_password_fast("Orient@2026")
    db.session.add(conseiller)

    chef_travaux_stt = User(username="cheftravaux.stt", role="chef_travaux", full_name="Chef des Travaux STT",
                             email="cheftravaux.stt@lycee-tibati.cm", section_id=section_map["STT"].id)
    chef_travaux_stt.set_password_fast("TravauxSTT@2026")
    db.session.add(chef_travaux_stt)

    chef_travaux_ind = User(username="cheftravaux.ind", role="chef_travaux", full_name="Chef des Travaux Industriel",
                             email="cheftravaux.ind@lycee-tibati.cm", section_id=section_map["IND"].id)
    chef_travaux_ind.set_password_fast("TravauxIND@2026")
    db.session.add(chef_travaux_ind)

    chef_crm = User(username="chefcrm1", role="chef_crm", full_name="Chef de Centre CRM",
                     email="chefcrm1@lycee-tibati.cm")
    chef_crm.set_password_fast("CentreCRM@2026")
    db.session.add(chef_crm)
    db.session.flush()

    # --- Salles / Ateliers / Équipements ---
    # Une salle "banalisée" dédiée par classe (2nde à Tle, toutes filières confondues),
    # afin que chaque niveau de chaque filière dispose de son propre local pour les cours théoriques.
    rooms = []
    n_classes = SchoolClass.query.count()
    for i in range(1, n_classes + 4):  # + quelques salles supplémentaires en réserve
        r = Room(name=f"Salle {i:02d}", type="Salle", capacity=48, location=f"Bâtiment A - Étage {1 if i <= (n_classes+4)//2 else 2}")
        db.session.add(r); rooms.append(r)

    # Ateliers/laboratoires spécialisés — un par filière technique, pour les enseignements pratiques
    ATELIER_MAP = {
        "GEL": "Atelier Électrotechnique",
        "IH": "Atelier Couture",
        "AMEB": "Atelier Menuiserie",
        "GC": "Atelier Génie Civil",
        "ACA": "Atelier Bureautique",
        "ESF": "Atelier Économie Familiale",
        "CG": "Salle Comptabilité & Gestion",
    }
    atelier_rooms = {}
    for dcode, name in ATELIER_MAP.items():
        r = Room(name=name, type="Atelier", capacity=30, location="Bâtiment Technique",
                 department_id=dept_map[dcode].id)
        db.session.add(r); rooms.append(r)
        atelier_rooms[dcode] = r
    # Centre de Ressources Multimédia — salle commune aux matières générales des deux sections
    crm_room = Room(name="Centre de Ressources Multimédia (CRM)", type="Laboratoire", capacity=40,
                     location="Bâtiment Central")
    db.session.add(crm_room); rooms.append(crm_room)
    db.session.flush()

    # Attribution d'une salle de classe dédiée (homeroom) à chaque classe, du 2nde à la Tle
    home_room = {}
    generic_rooms = [r for r in rooms if r.type == "Salle"]
    for i, cls in enumerate(SchoolClass.query.order_by(SchoolClass.department_id, SchoolClass.level).all()):
        room = generic_rooms[i % len(generic_rooms)]
        room.department_id = cls.department_id  # rattache la salle à la filière/section pour le Chef des Travaux
        home_room[cls.id] = room
    equip_names = ["Ordinateurs de bureau", "Postes de soudure", "Multimètres", "Vidéoprojecteur",
                   "Tour à métaux", "Automates programmables", "Table de dessin"]
    for r in atelier_rooms.values():
        for _ in range(2):
            db.session.add(Equipment(name=random.choice(equip_names), room_id=r.id,
                                      status=random.choice(["Opérationnel", "Opérationnel", "En maintenance"]),
                                      quantity=random.randint(2, 15)))
    db.session.flush()

    # --- Enseignants (2 par filière) ---
    all_depts = Department.query.all()
    teachers = []
    used_usernames = set()
    for dept in all_depts:
        n = 2
        for i in range(n):
            sex = random.choice(["M", "F"])
            fn, ln = rand_name(sex)
            base = slugify(f"{fn}.{ln}")
            uname = base
            k = 1
            while uname in used_usernames:
                k += 1
                uname = f"{base}{k}"
            used_usernames.add(uname)
            u = User(username=uname, role="enseignant", full_name=f"{fn} {ln}",
                     email=f"{uname}@lycee-tibati.cm")
            u.set_password_fast("Enseigner@2026")
            db.session.add(u)
            db.session.flush()
            t = Teacher(user_id=u.id, specialty=dept.name, department_id=dept.id,
                        grade=random.choice(["PLEG", "PLET", "PCEG", "PCET", "IGE"]),
                        hours_due=random.choice([15, 18, 20]),
                        extra_hours=random.choice([0, 0, 0, 2, 4]),
                        hire_date=date(random.randint(2010, 2024), random.randint(1, 12), random.randint(1, 28)))
            db.session.add(t)
            db.session.flush()
            teachers.append(t)
            db.session.add(Availability(teacher_id=t.id, day=random.choice(
                ["Lundi", "Mercredi", "Vendredi"]), start_time="15:00", end_time="16:00",
                note="Disponible pour rendez-vous parents"))
    db.session.flush()

    # comptes démo enseignants explicites (faciles à utiliser)
    demo_map = {"demo.aca": "ACA", "demo.ge": "GEL", "demo.ih": "IH"}
    demo_teachers = {}
    for uname, dcode in demo_map.items():
        dept = dept_map[dcode]
        u = User(username=uname, role="enseignant", full_name=f"Enseignant Démo ({dcode})",
                 email=f"{uname}@lycee-tibati.cm")
        u.set_password_fast("Demo@2026")
        db.session.add(u); db.session.flush()
        t = Teacher(user_id=u.id, specialty=dept.name, department_id=dept.id, grade="PLET",
                    hours_due=18, extra_hours=0, hire_date=date(2020, 9, 1))
        db.session.add(t); db.session.flush()
        teachers.append(t)
        demo_teachers[dcode] = t
    db.session.flush()

    # --- Cours : associer matières de chaque filière aux classes, avec un enseignant du département ---
    dept_teachers = {}
    for t in teachers:
        dept_teachers.setdefault(t.department_id, []).append(t)

    all_courses = []
    for dept in all_depts:
        avail_teachers = dept_teachers.get(dept.id, [])
        if not avail_teachers:
            continue
        for cls in dept.classes:
            for subj in dept.subjects:
                teacher = random.choice(avail_teachers)
                c = Course(subject_id=subj.id, teacher_id=teacher.id, class_id=cls.id)
                db.session.add(c)
                all_courses.append(c)
            # Professeur principal de la classe : un enseignant du département
            cls.homeroom_teacher_id = random.choice(avail_teachers).id
    db.session.flush()

    # --- Emplois du temps (grille officielle à 9 créneaux/jour, du 2nde à la Tle, pour chaque filière) ---
    # Cours théoriques -> salle dédiée de la classe (homeroom) ; matières pratiques -> atelier/labo de la filière.
    from utils import OFFICIAL_PERIODS
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    day_periods = OFFICIAL_PERIODS[:6]  # créneaux 1 à 6 (matin + début d'après-midi), comme dans les grilles réelles
    teacher_busy = set()  # (teacher_id, day, start) déjà occupés, pour éviter les conflits dans les données de démo
    for cls in SchoolClass.query.all():
        dept_code = cls.department.code
        practical_subject_names = {s[0] for s in TECH_EXTRA_SUBJECTS.get(dept_code, []) if s[2] == PR}
        courses_of_class = [c for c in all_courses if c.class_id == cls.id]
        if not courses_of_class:
            continue
        slot_list = [(day, p) for day in days for p in day_periods]
        random.shuffle(slot_list)
        course_cycle = (courses_of_class * (len(slot_list) // len(courses_of_class) + 1))
        random.shuffle(course_cycle)
        ptr = 0
        for day, (start, end) in slot_list:
            placed = False
            for _ in range(min(len(course_cycle), 20)):
                c = course_cycle[ptr % len(course_cycle)]
                ptr += 1
                key = (c.teacher_id, day, start)
                if key not in teacher_busy:
                    teacher_busy.add(key)
                    if c.subject.name in practical_subject_names and dept_code in atelier_rooms:
                        room = atelier_rooms[dept_code]
                    else:
                        room = home_room.get(cls.id, generic_rooms[0])
                    db.session.add(ScheduleEntry(course_id=c.id, room_id=room.id, day=day,
                                                  start_time=start, end_time=end, published=True))
                    placed = True
                    break
            # si aucune matière disponible sans conflit enseignant, le créneau reste libre
    db.session.flush()

    # --- Parents ---
    def make_parent():
        sex = random.choice(["M", "F"])
        fn, ln = rand_name(sex)
        base = slugify(f"{fn}.{ln}")
        uname = base
        k = 1
        while uname in used_usernames:
            k += 1
            uname = f"{base}{k}"
        used_usernames.add(uname)
        u = User(username=uname, role="parent", full_name=f"{fn} {ln}", email=f"{uname}@gmail.com")
        u.set_password_fast("Parent@2026")
        db.session.add(u); db.session.flush()
        p = Parent(user_id=u.id, phone=f"6{random.randint(50000000,79999999)}",
                   profession=random.choice(["Commerçant(e)", "Fonctionnaire", "Cultivateur(trice)", "Enseignant(e)", "Sans emploi"]))
        db.session.add(p); db.session.flush()
        return p

    # --- Élèves (environ 20 par classe) ---
    matricule_counter = 100001
    all_classes = SchoolClass.query.all()
    demo_students = []
    for cls in all_classes:
        n = random.randint(18, 28)
        for i in range(n):
            sex = random.choice(["M", "F"])
            fn, ln = rand_name(sex)
            matricule = f"LTT{matricule_counter}"
            matricule_counter += 1
            st = Student(matricule=matricule, first_name=fn, last_name=ln, sex=sex,
                         dob=date(random.randint(2005, 2009), random.randint(1, 12), random.randint(1, 28)),
                         birth_place=random.choice(BIRTH_PLACES),
                         address=f"Quartier {random.choice(['Centre', 'Nord', 'Sud', 'Marché'])}, Tibati",
                         class_id=cls.id, status="Inscrit", is_repeater=(random.random() < 0.08))
            db.session.add(st); db.session.flush()
            parent = make_parent()
            st.parents.append(parent)
            demo_students.append((st, cls))
    db.session.flush()

    # comptes démo élève + parent explicites (avec identifiants faciles), rattachés à une classe ACA
    demo_class = SchoolClass.query.filter_by(name="1ère ACA").first() or all_classes[0]
    u_eleve = User(username="demo.eleve", role="eleve", full_name="Élève Démo", email="demo.eleve@lycee-tibati.cm")
    u_eleve.set_password_fast("Demo@2026")
    db.session.add(u_eleve); db.session.flush()
    demo_student = Student(user_id=u_eleve.id, matricule="LTT999001", first_name="Élève", last_name="Démo",
                            sex="M", dob=date(2007, 5, 12), birth_place="Tibati", address="Centre-ville, Tibati",
                            class_id=demo_class.id, status="Inscrit", is_repeater=False)
    db.session.add(demo_student); db.session.flush()

    u_parent = User(username="demo.parent", role="parent", full_name="Parent Démo", email="demo.parent@gmail.com")
    u_parent.set_password_fast("Demo@2026")
    db.session.add(u_parent); db.session.flush()
    demo_parent = Parent(user_id=u_parent.id, phone="677000000", profession="Fonctionnaire")
    db.session.add(demo_parent); db.session.flush()
    demo_parent.children.append(demo_student)
    db.session.flush()

    # --- Notes, absences, sanctions, récompenses (échantillon réaliste) ---
    TERM_SEQ = {"Trimestre 1": (1, 2), "Trimestre 2": (3, 4), "Trimestre 3": (5, 6)}

    def add_sequence_grades(student_id, course_id, term):
        seq_a, seq_b = TERM_SEQ[term]
        db.session.add(Grade(value=round(random.uniform(5, 19), 1), max_value=20, type="Devoir",
                              term=term, student_id=student_id, course_id=course_id,
                              appreciation=random.choice(["Bon travail", "Peut mieux faire", "Excellent", "Effort à poursuivre"])))
        db.session.add(Grade(value=round(random.uniform(4, 19), 1), max_value=20, type="Évaluation", sequence=seq_a,
                              term=term, student_id=student_id, course_id=course_id))
        db.session.add(Grade(value=round(random.uniform(4, 19), 1), max_value=20, type="Évaluation", sequence=seq_b,
                              term=term, student_id=student_id, course_id=course_id))

    terms = ["Trimestre 1"]
    # Échantillon de notes réparti sur TOUTES les classes (et non les 250 premiers élèves toutes classes confondues,
    # ce qui laissait la plupart des classes totalement sans notes — bug trouvé sur un bulletin vide en conditions réelles).
    students_by_class = {}
    for st, cls in demo_students:
        students_by_class.setdefault(cls.id, []).append(st)
    sample_students = []
    for cls_id, students_in_class in students_by_class.items():
        sample_students.extend(random.sample(students_in_class, min(12, len(students_in_class))))
    for st in sample_students + [demo_student]:
        cls_courses = [c for c in all_courses if c.class_id == st.class_id]
        for c in random.sample(cls_courses, min(4, len(cls_courses))):
            for term in terms:
                add_sequence_grades(st.id, c.id, term)
        if random.random() < 0.35:
            c = random.choice(cls_courses)
            db.session.add(Attendance(date=date(2025, 10, random.randint(1, 28)), start_time="07:30", end_time="09:30",
                                       type=random.choice(["Absence", "Retard"]),
                                       reason=random.choice(["Maladie", "Non justifié", "Transport"]),
                                       justified=random.choice([True, False]),
                                       student_id=st.id, course_id=c.id))
        if random.random() < 0.06:
            db.session.add(Sanction(student_id=st.id, type=random.choice(["Avertissement (conduite)", "Blâme (conduite)", "Convocation des parents"]),
                                     description="Comportement perturbateur en classe", date=date(2025, 11, 5),
                                     issued_by_id=surveillant.id))
        if random.random() < 0.1:
            db.session.add(Reward(student_id=st.id, description=random.choice(
                ["Tableau d'honneur", "Meilleure moyenne de la classe", "Assiduité exemplaire"]),
                date=date(2025, 11, 20), issued_by_id=directeurs[0].id))
    db.session.flush()

    # notes garanties pour l'élève démo sur toutes ses matières (pour un bulletin complet)
    demo_courses = [c for c in all_courses if c.class_id == demo_student.class_id]
    for c in demo_courses:
        add_sequence_grades(demo_student.id, c.id, "Trimestre 1")

    # --- Réservations & maintenance ---
    for _ in range(6):
        db.session.add(Reservation(room_id=random.choice(rooms).id, purpose="Conseil de classe",
                                    date=date(2025, 12, random.randint(1, 15)), start_time="14:00", end_time="16:00",
                                    requested_by_id=censeur.id, status="Confirmée"))
    for _ in range(5):
        db.session.add(MaintenanceRequest(room_id=random.choice(rooms).id,
                                           description=random.choice(["Climatiseur en panne", "Prises électriques défectueuses",
                                                                        "Vidéoprojecteur ne s'allume plus", "Chaises à remplacer"]),
                                           status=random.choice(["Ouverte", "En cours", "Résolue"]),
                                           date=date(2025, 11, random.randint(1, 28)),
                                           reported_by_id=random.choice(teachers).user_id))

    # --- Annonces ---
    db.session.add(Announcement(title="Rentrée scolaire 2025-2026", body="La rentrée officielle aura lieu le 1er septembre. Tous les élèves doivent être en tenue réglementaire.", author_id=directeurs[0].id, target_role="tous"))
    db.session.add(Announcement(title="Conseils de classe du 1er trimestre", body="Les conseils de classe se tiendront du 15 au 20 décembre. Les enseignants doivent finaliser la saisie des notes avant le 12 décembre.", author_id=censeur.id, target_role="enseignant"))
    db.session.add(Announcement(title="Réunion des parents d'élèves", body="Une réunion d'information se tiendra le samedi 6 décembre à 9h en salle polyvalente.", author_id=directeurs[0].id, target_role="parent"))

    # --- Activités du personnel ---
    for t in random.sample(teachers, min(10, len(teachers))):
        db.session.add(ActivityLog(user_id=t.user_id, description=random.choice(
            ["Correction des copies du devoir n°1", "Réunion pédagogique de département",
             "Préparation des supports de cours", "Suivi individuel d'élèves en difficulté"]),
            category=random.choice(["pédagogique", "administrative"])))

    # --- Un message de bienvenue au parent démo ---
    db.session.add(Message(sender_id=censeur.id, recipient_id=u_parent.id,
                            subject="Bienvenue sur la plateforme",
                            body="Bonjour, bienvenue sur la plateforme numérique du Lycée Technique de Tibati. Vous pouvez désormais suivre la scolarité de votre enfant en ligne."))

    # --- Calendrier scolaire (modifiable ensuite par le Proviseur) ---
    for i, (label, date_text) in enumerate([
        ("Rentrée scolaire", "01/09/2025"),
        ("1er Trimestre", "01/09 – 20/12/2025"),
        ("2ème Trimestre", "06/01 – 04/04/2026"),
        ("3ème Trimestre", "20/04 – 20/06/2026"),
        ("Conseils de classe (T1)", "15 – 20/12/2025"),
    ]):
        db.session.add(SchoolCalendarEvent(label=label, date_text=date_text, position=i))

    db.session.commit()
    print("Base de données initialisée avec succès.")
