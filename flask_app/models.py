from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

ROLES = ["directeur", "censeur", "censeur_crm", "surveillant_general", "conseiller_orientation", "chef_travaux", "chef_crm", "enseignant", "eleve", "parent"]
STAFF_GRADES = ["Instituteur", "PLEG", "PLET", "PCEG", "PCET", "IGE", "IPR", "CPE"]
ROLE_LABELS = {
    "directeur": "Proviseur",
    "censeur": "Censeur",
    "censeur_crm": "Censeur CRM",
    "surveillant_general": "Surveillant Général",
    "conseiller_orientation": "Conseiller d'Orientation",
    "chef_travaux": "Chef des Travaux",
    "chef_crm": "Chef de Centre CRM",
    "enseignant": "Enseignant",
    "eleve": "Élève",
    "parent": "Parent",
}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    plain_password = db.Column(db.String(64))  # copie lisible, réservée à la consultation par le Proviseur (dépannage identifiants)
    role = db.Column(db.String(40), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    civility = db.Column(db.String(4))
    active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    session_token = db.Column(db.String(64), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"))  # portée du compte (Censeur/Surveillant Général/Chef des Travaux) — vide = transversal (ex. Censeur Enseignements Généraux)
    section = db.relationship("Section")
    grade = db.Column(db.String(30))  # grade administratif (Censeur/Proviseur) — distinct du grade enseignant sur Teacher

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)
        self.plain_password = pw

    def set_password_fast(self, pw):
        """Hachage allégé, réservé au peuplement initial de centaines de comptes de démonstration.
        Les comptes créés via l'interface (un par un) utilisent set_password() avec le coût sécurisé par défaut."""
        self.password_hash = generate_password_hash(pw, method="pbkdf2:sha256:20000")
        self.plain_password = pw

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def formal_name(self):
        """Nom à afficher avec la civilité lorsqu’elle est renseignée."""
        return f"{self.civility} {self.full_name}" if self.civility else self.full_name

    @property
    def scope_label(self):
        """Libellé de la portée du compte pour l'affichage (ex. 'Censeur STT')."""
        if self.role == "censeur":
            return f"Censeur {self.section.code}" if self.section else "Censeur Enseignements Généraux"
        if self.role == "surveillant_general":
            return f"Surveillant Général {self.section.code}" if self.section else "Surveillant Général"
        if self.role == "chef_travaux":
            return f"Chef des Travaux {self.section.code}" if self.section else "Chef des Travaux"
        return self.role_label

    @property
    def initials(self):
        parts = self.full_name.split()
        return "".join(p[0] for p in parts[:2]).upper() if parts else "?"


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    code = db.Column(db.String(20))
    departments = db.relationship("Department", backref="section", cascade="all, delete-orphan")


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(10), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=False)
    capacity = db.Column(db.Integer, default=48)
    classes = db.relationship("SchoolClass", backref="department", cascade="all, delete-orphan")
    subjects = db.relationship("Subject", backref="department", cascade="all, delete-orphan")


class SchoolClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False)  # e.g. 2nde ACA
    level = db.Column(db.String(20), nullable=False)  # 2nde/1ere/Tle
    specialty = db.Column(db.String(30))  # code de spécialité tel qu'utilisé par l'établissement (ex. ELEQ, F3) — peut différer du code de la filière selon le cycle
    code = db.Column(db.String(30), unique=True)  # identifiant unique de la classe, saisi par le Proviseur
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    school_year = db.Column(db.String(12), default="2025-2026")
    capacity = db.Column(db.Integer, default=48)
    homeroom_teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"))  # professeur principal
    students = db.relationship("Student", backref="school_class")
    courses = db.relationship("Course", backref="school_class", cascade="all, delete-orphan")
    homeroom_teacher = db.relationship("Teacher", foreign_keys=[homeroom_teacher_id])


SUBJECT_CATEGORIES = [
    "Enseignements Généraux",
    "Enseignements Professionnels Théoriques",
    "Enseignements Professionnels Pratiques",
    "Enseignements Divers",
]


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    coefficient = db.Column(db.Integer, nullable=True, default=1)
    category = db.Column(db.String(60), nullable=True, default="Enseignements Généraux")
    timetable_only = db.Column(db.Boolean, nullable=False, default=False)  # matière planifiable sans notes ni bulletin
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"))
    courses = db.relationship("Course", backref="subject", cascade="all, delete-orphan")
    school_class = db.relationship("SchoolClass", backref="subjects")


teacher_availability = db.Table(
    "teacher_availability",
    db.Column("teacher_id", db.Integer, db.ForeignKey("teacher.id")),
)


class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    specialty = db.Column(db.String(120))
    hire_date = db.Column(db.Date)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    grade = db.Column(db.String(30), default="PLET")  # grade académique (PLEG, PLET, PCEG...)
    hours_due = db.Column(db.Integer, default=18)  # heures dues hebdomadaires
    extra_hours = db.Column(db.Integer, default=0)  # heures supplémentaires
    user = db.relationship("User", backref=db.backref("teacher_profile", uselist=False))
    department = db.relationship("Department", backref="teachers")
    courses = db.relationship("Course", backref="teacher")


class TeacherIndicator(db.Model):
    """Indicateurs pédagogiques trimestriels renseignés par l'enseignant lui-même
    (couverture des heures, des programmes, des travaux pratiques) — alimente la synthèse
    du conseil de classe et le rapport transmis au Ministère."""
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"))  # classe + matière concernées
    term = db.Column(db.String(20), default="Trimestre 1")
    hours_due = db.Column(db.Integer, default=0)
    hours_done = db.Column(db.Integer, default=0)
    lessons_planned = db.Column(db.Integer, default=0)
    lessons_done = db.Column(db.Integer, default=0)
    digital_lessons_planned = db.Column(db.Integer, default=0)
    digital_lessons_done = db.Column(db.Integer, default=0)
    tp_planned = db.Column(db.Integer, default=0)
    tp_done = db.Column(db.Integer, default=0)
    digital_tp_planned = db.Column(db.Integer, default=0)
    digital_tp_done = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    teacher = db.relationship("Teacher", backref="indicators")
    course = db.relationship("Course")


class CustomIndicatorType(db.Model):
    """Type d'indicateur pédagogique supplémentaire défini par un Censeur (en plus des indicateurs
    standards) — apparaît ensuite chez les enseignants concernés (portée = section du Censeur qui l'a créé,
    ou transversal si créé par le Proviseur/Censeur Enseignements Généraux)."""
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    unit_planned = db.Column(db.String(30), default="Prévu")   # libellé de la colonne "prévu"
    unit_done = db.Column(db.String(30), default="Fait")       # libellé de la colonne "fait/réalisé"
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"))  # vide = visible dans toutes les sections
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    section = db.relationship("Section")
    created_by = db.relationship("User")


class CustomIndicatorValue(db.Model):
    """Valeur d'un indicateur personnalisé, saisie par l'enseignant pour une classe/matière/trimestre."""
    id = db.Column(db.Integer, primary_key=True)
    indicator_type_id = db.Column(db.Integer, db.ForeignKey("custom_indicator_type.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    term = db.Column(db.String(20), default="Trimestre 1")
    planned = db.Column(db.Integer, default=0)
    done = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    indicator_type = db.relationship("CustomIndicatorType", backref=db.backref("values", cascade="all, delete-orphan"))
    course = db.relationship("Course")


class Availability(db.Model):
    """Créneaux de disponibilité déclarés par un enseignant (réunions/entretiens)."""
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    day = db.Column(db.String(12), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    note = db.Column(db.String(160))
    teacher = db.relationship("Teacher", backref="availabilities")


class ActivityLog(db.Model):
    """Suivi des activités pédagogiques/administratives des enseignants et staff."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(40), default="pédagogique")
    user = db.relationship("User")


class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    profession = db.Column(db.String(120))
    user = db.relationship("User", backref=db.backref("parent_profile", uselist=False))


student_parent = db.Table(
    "student_parent",
    db.Column("student_id", db.Integer, db.ForeignKey("student.id"), primary_key=True),
    db.Column("parent_id", db.Integer, db.ForeignKey("parent.id"), primary_key=True),
)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    matricule = db.Column(db.String(30), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    dob = db.Column(db.Date)
    sex = db.Column(db.String(1))
    address = db.Column(db.String(200))
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"))
    status = db.Column(db.String(20), default="Inscrit")  # Inscrit / Réinscrit / En attente
    is_repeater = db.Column(db.Boolean, default=False)  # Redoublant
    birth_place = db.Column(db.String(120))
    photo = db.Column(db.String(200))  # nom de fichier dans static/uploads/students/
    enrolled_on = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref=db.backref("student_profile", uselist=False))
    parents = db.relationship("Parent", secondary=student_parent, backref="children")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Course(db.Model):
    """Association matière + enseignant + classe (ce qui est enseigné à qui)."""
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=False)
    grades = db.relationship("Grade", backref="course", cascade="all, delete-orphan")
    attendances = db.relationship("Attendance", backref="course", cascade="all, delete-orphan")
    schedule_entries = db.relationship("ScheduleEntry", backref="course", cascade="all, delete-orphan")


class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float, nullable=False)
    max_value = db.Column(db.Float, default=20)
    type = db.Column(db.String(20), default="Devoir")  # Devoir (continu) / Évaluation
    sequence = db.Column(db.Integer)  # 1 à 6 quand type == "Évaluation" (2 évaluations par trimestre)
    term = db.Column(db.String(20), default="Trimestre 1")
    date = db.Column(db.Date, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    appreciation = db.Column(db.String(160))
    student = db.relationship("Student", backref="grades")


class BulletinApproval(db.Model):
    """Validation de diffusion d'un bulletin pour une classe et un trimestre."""
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Validé")
    validated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    validated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    official_release_date = db.Column(db.Date, nullable=True)
    revoked_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revocation_reason = db.Column(db.Text, nullable=True)
    school_class = db.relationship("SchoolClass", backref="bulletin_approvals")
    validated_by = db.relationship("User", foreign_keys=[validated_by_id])
    revoked_by = db.relationship("User", foreign_keys=[revoked_by_id])
    __table_args__ = (db.UniqueConstraint("class_id", "term", name="uq_bulletin_approval_class_term"),)


class BulletinWorkAppreciation(db.Model):
    """Appréciation générale du travail, saisie par le Censeur pour un élève et un trimestre."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)
    student = db.relationship("Student", backref="bulletin_work_appreciations")
    updated_by = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("student_id", "term", name="uq_bulletin_work_appreciation_student_term"),)


class PlannedAssessment(db.Model):
    """Évaluation programmée par cours, période et séquence, suivie jusqu’à la saisie complète des notes."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    term = db.Column(db.String(20), default="Trimestre 1", nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    max_value = db.Column(db.Float, default=20)
    status = db.Column(db.String(30), default="Planifiée")
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    course = db.relationship("Course", backref="planned_assessments")
    created_by = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("course_id", "term", "sequence", name="uq_planned_assessment_course_term_sequence"),)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow)
    start_time = db.Column(db.String(5))
    end_time = db.Column(db.String(5))
    type = db.Column(db.String(12), default="Absence")  # Absence / Retard
    reason = db.Column(db.String(200))
    justified = db.Column(db.Boolean, default=False)
    justification_note = db.Column(db.String(300))
    justification_requested_at = db.Column(db.DateTime)
    justified_at = db.Column(db.DateTime)
    justified_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"))
    student = db.relationship("Student", backref="attendances")
    justified_by = db.relationship("User", foreign_keys=[justified_by_id])
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])


class Sanction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    type = db.Column(db.String(60), nullable=False)  # Avertissement / Blâme / Convocation / Exclusion temporaire
    description = db.Column(db.String(255))
    date = db.Column(db.Date, default=datetime.utcnow)
    issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    student = db.relationship("Student", backref="sanctions")
    issued_by = db.relationship("User")


class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    student = db.relationship("Student", backref="rewards")
    issued_by = db.relationship("User")


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(30), default="Salle")  # Salle / Atelier / Laboratoire / CRM
    capacity = db.Column(db.Integer, default=40)
    location = db.Column(db.String(120))
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))  # rattachement pour le Chef des Travaux de la section — vide = commun (ex. CRM)
    department = db.relationship("Department")
    equipments = db.relationship("Equipment", backref="room", cascade="all, delete-orphan")
    schedule_entries = db.relationship("ScheduleEntry", backref="room", cascade="all, delete-orphan")
    reservations = db.relationship("Reservation", backref="room", cascade="all, delete-orphan")
    maintenance_requests = db.relationship("MaintenanceRequest", backref="room", cascade="all, delete-orphan",
                                            foreign_keys="MaintenanceRequest.room_id")


class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"))
    status = db.Column(db.String(20), default="Opérationnel")  # Opérationnel / En panne / En maintenance
    quantity = db.Column(db.Integer, default=1)


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    purpose = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    status = db.Column(db.String(20), default="Confirmée")
    requested_by = db.relationship("User")


class MaintenanceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"))
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"))
    description = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="Ouverte")  # Ouverte / En cours / Résolue
    date = db.Column(db.Date, default=datetime.utcnow)
    reported_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    equipment = db.relationship("Equipment")
    reported_by = db.relationship("User")


class ScheduleEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=True)
    day = db.Column(db.String(12), nullable=False)  # Lundi..Samedi
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    published = db.Column(db.Boolean, default=False)
    group_key = db.Column(db.String(36))  # identifiant partagé pour un cours en tronc commun (plusieurs classes réunies) — vide sinon


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])


class Correspondence(db.Model):
    """Entrée officielle du carnet de correspondance, liée à un élève et distribuée à ses responsables."""
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    category = db.Column(db.String(40), default="Information")
    priority = db.Column(db.String(20), default="Normale")
    subject = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship("User", foreign_keys=[author_id])
    student = db.relationship("Student", backref="correspondence_entries")
    receipts = db.relationship("CorrespondenceReceipt", backref="entry", cascade="all, delete-orphan")


class CorrespondenceReceipt(db.Model):
    """Traçabilité individuelle de lecture et d’accusé de réception du carnet."""
    id = db.Column(db.Integer, primary_key=True)
    correspondence_id = db.Column(db.Integer, db.ForeignKey("correspondence.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    read_at = db.Column(db.DateTime)
    acknowledged_at = db.Column(db.DateTime)
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("correspondence_id", "user_id", name="uq_correspondence_receipt"),)


class AppSetting(db.Model):
    """Paramètres globaux de l'établissement (un seul enregistrement) — modifiables par le Proviseur,
    utilisés partout où l'année scolaire doit s'afficher (bulletins, emplois du temps, exports…)."""
    id = db.Column(db.Integer, primary_key=True)
    current_school_year = db.Column(db.String(12), default="2025-2026")


class SchoolCalendarEvent(db.Model):
    """Événement du calendrier scolaire (rentrée, trimestres, conseils de classe, vacances, examens…)
    affiché sur les tableaux de bord Proviseur/Censeur — modifiable par le Proviseur."""
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    date_text = db.Column(db.String(60), nullable=False)  # texte libre : "01/09/2025" ou "01/09 – 20/12/2025"
    position = db.Column(db.Integer, default=0)  # ordre d'affichage


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    target_role = db.Column(db.String(20), default="tous")  # tous/enseignant/eleve/parent
    author = db.relationship("User")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(255))
    user = db.relationship("User")
