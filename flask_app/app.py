import os
import json
import random
import secrets
from datetime import datetime, date, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from flask import Flask, Response, render_template, request, redirect, url_for, session, flash, abort, jsonify
from sqlalchemy.exc import OperationalError

from models import (
    db, User, Section, Department, SchoolClass, Subject, Teacher, Parent, Student,
    Course, Grade, Attendance, Sanction, Reward, Room, Equipment, Reservation,
    ScheduleEntry, Message, Announcement, Notification, MaintenanceRequest,
    Availability, ActivityLog, BulletinApproval, ROLES, ROLE_LABELS,
)
from utils import (
    login_required, roles_required, notify, student_average, subject_averages,
    general_average, check_schedule_conflict, parse_date, DAYS, TERMS, generate_account_password,
)
import seed as seed_module

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["ENVIRONMENT"] = os.getenv("LTT_ENV", "development")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.config["SECRET_KEY"] = os.getenv("LTT_SECRET_KEY") or os.getenv("SECRET_KEY") or "ltt-dev-secret-change-before-production"
database_url = os.getenv("DATABASE_URL") or f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ltt.db')}"
if database_url.startswith("mysql://"):
    database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
if database_url.startswith("mysql+pymysql://"):
    parsed_database_url = urlsplit(database_url)
    database_query = [(key, value) for key, value in parse_qsl(parsed_database_url.query, keep_blank_values=True)
                      if key.lower() not in {"ssl", "sslmode"}]
    database_url = urlunsplit((parsed_database_url.scheme, parsed_database_url.netloc,
                               parsed_database_url.path, urlencode(database_query), parsed_database_url.fragment))
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
if database_url.startswith("mysql+pymysql://"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"ssl": {"ca": None}},
        "pool_pre_ping": True,
        "pool_recycle": 240,
        "pool_timeout": 20,
    }
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("LTT_COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

LTT_ASSETS = {
    "css/style.css": "/manus-storage/style_fabb8241.css",
    "img/avatar_placeholder.png": "/manus-storage/avatar_placeholder_0074e93d.png",
    "img/logo.png": "/manus-storage/logo_1bfe095c.png",
    "img/logo.svg": "/manus-storage/logo_83de0e49.svg",
    "img/hero/couture.jpg": "/manus-storage/couture_8afe4400.jpg",
    "img/hero/cuisine.jpg": "/manus-storage/cuisine_8b65c9cb.jpg",
    "img/hero/electricite.jpg": "/manus-storage/electricite_45fe4f51.jpg",
    "img/hero/informatique.jpg": "/manus-storage/informatique_e56b28f0.jpg",
    "img/hero/maconnerie.jpg": "/manus-storage/maconnerie_3610ec86.jpg",
    "img/hero/mecanique.jpg": "/manus-storage/mecanique_e88cb2c4.jpg",
    "img/hero/menuiserie.jpg": "/manus-storage/menuiserie_3d26771b.jpg",
    "vendor/chartjs/chart.js": "/manus-storage/chart_ea4567ab.js",
    "vendor/css/bootstrap.min.css": "/manus-storage/bootstrap.min_764ee383.css",
    "vendor/icons/bootstrap-icons.min.css": "/manus-storage/bootstrap-icons.min_16fc5d8a.css",
    "vendor/js/bootstrap.bundle.min.js": "/manus-storage/bootstrap.bundle.min_733b2261.js",
}


def ltt_url_for(endpoint, **values):
    """Redirige les ressources lourdes vers le stockage WebDev sans toucher aux templates."""
    if endpoint == "static":
        filename = values.get("filename", "")
        return LTT_ASSETS.get(filename, url_for(endpoint, **values))
    return url_for(endpoint, **values)


def student_photo_url(photo):
    if photo and (photo.startswith("/manus-storage/") or photo.startswith("https://")):
        return photo
    if photo:
        return ltt_url_for("static", filename=f"uploads/students/{photo}")
    return ltt_url_for("static", filename="img/avatar_placeholder.png")


def dashboard_calendar_events():
    """Charge les événements de calendrier en reprenant une déconnexion MySQL ponctuelle."""
    from models import SchoolCalendarEvent
    try:
        return SchoolCalendarEvent.query.order_by(SchoolCalendarEvent.position).all()
    except OperationalError:
        db.session.rollback()
        db.session.remove()
        return SchoolCalendarEvent.query.order_by(SchoolCalendarEvent.position).all()


@app.get("/manifest.webmanifest")
def web_app_manifest():
    manifest = {
        "name": "Lycée Technique de Tibati — Plateforme numérique",
        "short_name": "LTT Tibati",
        "start_url": "/login",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0B2545",
        "theme_color": "#0B2545",
        "description": "Plateforme numérique de gestion du Lycée Technique de Tibati.",
        "icons": [
            {"src": LTT_ASSETS["img/logo.png"], "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": LTT_ASSETS["img/logo.png"], "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return Response(json.dumps(manifest), mimetype="application/manifest+json")


@app.get("/service-worker.js")
def service_worker():
    orbit_assets = [LTT_ASSETS[asset] for asset in (
        "img/hero/maconnerie.jpg", "img/hero/electricite.jpg", "img/hero/menuiserie.jpg",
        "img/hero/couture.jpg", "img/hero/informatique.jpg", "img/hero/cuisine.jpg", "img/hero/mecanique.jpg",
    )]
    assets = ["/manifest.webmanifest", LTT_ASSETS["css/style.css"], LTT_ASSETS["img/logo.png"], *orbit_assets]
    script = """
	const CACHE_NAME = 'ltt-shell-v20';
const ASSETS = __ASSETS__;
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)).catch(() => null).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !url.pathname.startsWith('/manus-storage/')) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy = response.clone(); caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)); return response;
  })));
});
"""
    script = script.replace("__ASSETS__", json.dumps(assets))
    return Response(script, mimetype="application/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/pwa-install.js")
def pwa_install_script():
    script = """
let installPrompt;
const installButtons = () => document.querySelectorAll('[data-pwa-install]');
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault(); installPrompt = event;
  installButtons().forEach(button => button.classList.remove('d-none'));
});
window.addEventListener('appinstalled', () => installButtons().forEach(button => button.classList.add('d-none')));
document.addEventListener('click', async event => {
  const button = event.target.closest('[data-pwa-install]');
  if (!button || !installPrompt) return;
  installPrompt.prompt(); await installPrompt.userChoice;
  installPrompt = null; installButtons().forEach(item => item.classList.add('d-none'));
});
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js'));
"""
    return Response(script, mimetype="application/javascript", headers={"Cache-Control": "no-cache"})

db.init_app(app)

with app.app_context():
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    db.create_all()
    if os.getenv("LTT_BOOTSTRAP_MODE", "founder") == "demo":
        seed_module.seed()
    else:
        seed_module.bootstrap_founder()


# ---------------------------------------------------------------- context ---
@app.context_processor
def inject_globals():
    from utils import get_current_school_year
    user = None
    unread_msgs = 0
    unread_notifs = 0
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        if user:
            _issue_bulletin_release_notifications(user)
            unread_msgs = Message.query.filter_by(recipient_id=user.id, read=False).count()
            unread_notifs = Notification.query.filter_by(user_id=user.id, read=False).count()
    return dict(current_user=user, unread_msgs=unread_msgs, unread_notifs=unread_notifs,
                ROLE_LABELS=ROLE_LABELS, now=datetime.utcnow(), school_year=get_current_school_year(),
                url_for=ltt_url_for, student_photo_url=student_photo_url)


def _issue_bulletin_release_notifications(user):
    """Crée une seule notification interne lorsque la date officielle de remise est atteinte."""
    approvals = BulletinApproval.query.filter(
        BulletinApproval.status == "Validé",
        BulletinApproval.official_release_date.isnot(None),
        BulletinApproval.official_release_date <= date.today(),
    ).all()
    if not approvals:
        return
    targets = []
    if user.role == "eleve" and user.student_profile:
        targets = [(user.student_profile, f"/eleve/notes")]
    elif user.role == "parent" and user.parent_profile:
        targets = [(child, f"/parent/enfant/{child.id}") for child in user.parent_profile.children]
    created = False
    for student, path in targets:
        for approval in approvals:
            if approval.class_id != student.class_id:
                continue
            link = f"{path}?term={approval.term.replace(' ', '+')}&remise={approval.id}"
            if Notification.query.filter_by(user_id=user.id, link=link).first():
                continue
            notify(user.id, f"Remise officielle — {approval.term} : le bulletin de {student.full_name} est remis aujourd’hui par le Censeur.", link)
            created = True
    if created:
        db.session.commit()


# -------------------------------------------------------------------- auth ---
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.active and user.check_password(password):
            session.clear()
            user.session_token = secrets.token_urlsafe(24)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            session["user_id"] = user.id
            session["role"] = user.role
            session["name"] = user.full_name
            session["session_token"] = user.session_token
            flash(f"Bienvenue, {user.full_name} !", "success")
            if user.must_change_password:
                return redirect(url_for("first_password_change"))
            return redirect(url_for("dashboard"))
        flash("Identifiant ou mot de passe incorrect.", "danger")
    from models import SchoolCalendarEvent
    upcoming_events = SchoolCalendarEvent.query.order_by(SchoolCalendarEvent.position).limit(3).all()
    public_announcements = Announcement.query.filter_by(target_role="tous").order_by(Announcement.date.desc()).limit(3).all()
    return render_template("login.html", upcoming_events=upcoming_events, public_announcements=public_announcements)


@app.before_request
def enforce_initial_password_change():
    """Garantit une session unique et empêche l’accès interne avant la première configuration."""
    if request.endpoint in {"login", "logout", "health", "static"} or not session.get("user_id"):
        return None
    user = User.query.get(session["user_id"])
    if (not user or not user.active or not session.get("session_token")
            or not user.session_token or not secrets.compare_digest(session["session_token"], user.session_token)):
        session.clear()
        flash("Session fermée : ce compte vient de se connecter depuis un autre appareil. Veuillez vous reconnecter si nécessaire.", "session_closed")
        return redirect(url_for("login"))
    if request.endpoint in {"login", "logout", "first_password_change"}:
        return None
    if user and user.must_change_password:
        flash("Veuillez définir votre mot de passe personnel avant de continuer.", "warning")
        return redirect(url_for("first_password_change"))
    return None


@app.route("/premiere-connexion", methods=["GET", "POST"])
@login_required
def first_password_change():
    user = User.query.get(session["user_id"])
    if not user or not user.must_change_password:
        return redirect(url_for("dashboard"))
    generated_password = user.plain_password
    if not generated_password:
        generated_password = generate_account_password(user.full_name, user.role)
        user.plain_password = generated_password
        db.session.commit()
    if request.method == "POST":
        user.set_password(generated_password)
        user.must_change_password = False
        db.session.commit()
        flash("Votre mot de passe personnel généré a été enregistré. Conservez-le dans un lieu sûr.", "success")
        return redirect(url_for("dashboard"))
    return render_template("first_password_change.html", user=user, generated_password=generated_password)


@app.route("/logout")
def logout():
    user = User.query.get(session.get("user_id")) if session.get("user_id") else None
    if user and session.get("session_token") and user.session_token == session.get("session_token"):
        user.session_token = None
        db.session.commit()
    session.clear()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("login"))


# --------------------------------------------------------------- dashboard ---
@app.route("/dashboard")
@login_required
def dashboard():
    role = session["role"]
    user = User.query.get(session["user_id"])

    if role == "directeur":
        stats = dict(
            students=Student.query.count(),
            teachers=Teacher.query.count(),
            parents=Parent.query.count(),
            classes=SchoolClass.query.count(),
            sections=Section.query.count(),
            rooms=Room.query.count(),
            absences_month=Attendance.query.filter_by(type="Absence").count(),
            sanctions=Sanction.query.count(),
            maintenance_open=MaintenanceRequest.query.filter(MaintenanceRequest.status != "Résolue").count(),
        )
        by_section = []
        for s in Section.query.all():
            n = sum(len(c.students) for d in s.departments for c in d.classes)
            by_section.append((s.name, n))
        recent_announcements = Announcement.query.order_by(Announcement.date.desc()).limit(5).all()
        from utils import dashboard_rates, department_success_rates, evolution_series, dashboard_alerts, recent_activity_feed
        rates = dashboard_rates()
        success_by_dept = department_success_rates()
        evolution = evolution_series()
        alerts = dashboard_alerts()
        activities = recent_activity_feed()
        calendar_events = dashboard_calendar_events()
        setup_steps = [
            {"label": "Structurer les sections et filières", "value": stats["sections"], "endpoint": "dir_structure", "icon": "bi-diagram-3-fill"},
            {"label": "Créer les classes", "value": stats["classes"], "endpoint": "dir_structure", "icon": "bi-building"},
            {"label": "Ajouter l’équipe éducative", "value": stats["teachers"], "endpoint": "dir_users", "icon": "bi-person-workspace"},
            {"label": "Déclarer les salles et ateliers", "value": stats["rooms"], "endpoint": "rooms_list", "icon": "bi-door-open-fill"},
            {"label": "Inscrire les premiers élèves", "value": stats["students"], "endpoint": "student_enroll", "icon": "bi-mortarboard-fill"},
        ]
        setup_progress = round(100 * sum(1 for item in setup_steps if item["value"] > 0) / len(setup_steps))
        chart_summary = {
            "labels": ["Filières", "Classes", "Équipe", "Élèves"],
            "values": [Department.query.count(), stats["classes"], stats["teachers"], stats["students"]],
        }
        total_capacity = sum((school_class.capacity or 0) for school_class in SchoolClass.query.all())
        school_summary = {
            "capacity": total_capacity,
            "available_seats": max(total_capacity - stats["students"], 0),
            "student_teacher_ratio": round(stats["students"] / stats["teachers"], 1) if stats["teachers"] else None,
            "classes_per_teacher": round(stats["classes"] / stats["teachers"], 1) if stats["teachers"] else None,
        }
        return render_template("dashboard_directeur.html", stats=stats, by_section=by_section,
                                announcements=recent_announcements, rates=rates, success_by_dept=success_by_dept,
                                evolution=evolution, alerts=alerts, activities=activities, calendar_events=calendar_events,
                                setup_steps=setup_steps, setup_progress=setup_progress, chart_summary=chart_summary,
                                school_summary=school_summary,
                                is_founder_setup=User.query.count() == 1 and stats["students"] == 0)

    if role == "censeur":
        from utils import user_scoped_class_ids, user_scoped_department_ids
        scoped_ids = user_scoped_class_ids(user)
        if scoped_ids is not None:
            students_count = Student.query.filter(Student.class_id.in_(scoped_ids)).count()
            teachers_count = Teacher.query.join(Department).filter(Department.section_id == user.section_id).count()
            schedules_count = ScheduleEntry.query.join(Course).filter(Course.class_id.in_(scoped_ids)).count()
        else:
            students_count = Student.query.count()
            teachers_count = Teacher.query.count()
            schedules_count = ScheduleEntry.query.count()
        recent_absences = Attendance.query.order_by(Attendance.date.desc()).limit(10).all()
        recent_sanctions = Sanction.query.order_by(Sanction.date.desc()).limit(5).all()
        stats = dict(students=students_count, teachers=teachers_count, rooms=Room.query.count())
        from utils import dashboard_rates, department_success_rates, evolution_series, dashboard_alerts, recent_activity_feed
        scoped_dept_ids = user_scoped_department_ids(user)
        subjects_count = Subject.query.filter(Subject.department_id.in_(scoped_dept_ids)).count() if scoped_dept_ids else Subject.query.count()
        stats = dict(students=students_count, teachers=teachers_count, rooms=Room.query.count(),
                     schedules=schedules_count, subjects=subjects_count)
        rates = dashboard_rates(scoped_ids)
        success_by_dept = department_success_rates(scoped_dept_ids)
        evolution = evolution_series(scoped_ids)
        alerts = dashboard_alerts(scoped_ids, scoped_dept_ids)
        activities = recent_activity_feed(scoped_ids, scoped_dept_ids)
        calendar_events = dashboard_calendar_events()
        return render_template("dashboard_censeur.html", rates=rates, success_by_dept=success_by_dept,
                                evolution=evolution, alerts=alerts, activities=activities,
                                recent_absences=recent_absences, recent_sanctions=recent_sanctions, stats=stats,
                                calendar_events=calendar_events)

    if role == "censeur_crm":
        general_courses = Course.query.join(Subject).filter(Subject.category == "Enseignements Généraux").all()
        stats = dict(students=Student.query.count(), teachers=len(set(c.teacher_id for c in general_courses)),
                     rooms=Room.query.count())
        from utils import dashboard_rates, department_success_rates, evolution_series, dashboard_alerts, recent_activity_feed
        rates = dashboard_rates()
        success_by_dept = department_success_rates()
        evolution = evolution_series()
        alerts = dashboard_alerts()
        activities = recent_activity_feed()
        calendar_events = dashboard_calendar_events()
        return render_template("dashboard_censeur.html", rates=rates, success_by_dept=success_by_dept,
                                evolution=evolution, alerts=alerts, activities=activities,
                                recent_absences=[], recent_sanctions=[], stats=stats, calendar_events=calendar_events)

    if role == "surveillant_general":
        from utils import user_scoped_class_ids
        scoped_ids = user_scoped_class_ids(user)
        att_q = Attendance.query
        sanction_q = Sanction.query
        reward_q = Reward.query
        students_count = Student.query.count()
        if scoped_ids is not None:
            att_q = att_q.join(Student).filter(Student.class_id.in_(scoped_ids))
            sanction_q = sanction_q.join(Student).filter(Student.class_id.in_(scoped_ids))
            reward_q = reward_q.join(Student).filter(Student.class_id.in_(scoped_ids))
            students_count = Student.query.filter(Student.class_id.in_(scoped_ids)).count()
        stats = dict(
            students=students_count,
            absences_month=att_q.filter(Attendance.type == "Absence").count(),
            retards_month=att_q.filter(Attendance.type == "Retard").count(),
            unjustified=att_q.filter(Attendance.justified == False).count(),  # noqa: E712
            sanctions=sanction_q.count(),
            rewards=reward_q.count(),
        )
        recent_absences = att_q.order_by(Attendance.date.desc()).limit(10).all()
        recent_sanctions = sanction_q.order_by(Sanction.date.desc()).limit(5).all()
        from utils import dashboard_alerts, dashboard_rates
        rates = dashboard_rates(scoped_ids)
        return render_template("dashboard_surveillant.html", stats=stats, rates=rates,
                                recent_absences=recent_absences, recent_sanctions=recent_sanctions,
                                life_alerts=dashboard_alerts(class_ids=scoped_ids))

    if role == "conseiller_orientation":
        stats = dict(
            students=Student.query.count(),
            parents=Parent.query.count(),
            teachers=Teacher.query.count(),
            classes=SchoolClass.query.count(),
        )
        recent_announcements = Announcement.query.order_by(Announcement.date.desc()).limit(5).all()
        from utils import dashboard_rates, dashboard_alerts, recent_activity_feed
        rates = dashboard_rates()
        alerts = dashboard_alerts()
        activities = recent_activity_feed()
        return render_template("dashboard_conseiller.html", stats=stats, announcements=recent_announcements,
                                rates=rates, alerts=alerts, activities=activities)

    if role in ("chef_travaux", "chef_crm"):
        from utils import user_scoped_department_ids
        scoped_ids = user_scoped_department_ids(user) if role == "chef_travaux" else None
        if role == "chef_crm":
            rooms_q = Room.query.filter(Room.department_id.is_(None))
        elif scoped_ids is not None:
            rooms_q = Room.query.filter(Room.department_id.in_(scoped_ids))
        else:
            rooms_q = Room.query
        room_ids = [r.id for r in rooms_q.all()]
        stats = dict(
            rooms=len(room_ids),
            ateliers=rooms_q.filter_by(type="Atelier").count(),
            laboratoires=rooms_q.filter_by(type="Laboratoire").count(),
            salles=rooms_q.filter_by(type="Salle").count(),
            equipments=Equipment.query.filter(Equipment.room_id.in_(room_ids)).count() if room_ids else 0,
            maintenance_open=MaintenanceRequest.query.filter(
                MaintenanceRequest.status != "Résolue", MaintenanceRequest.room_id.in_(room_ids)).count() if room_ids else 0,
        )
        recent_maintenance = (MaintenanceRequest.query.filter(MaintenanceRequest.room_id.in_(room_ids))
                               .order_by(MaintenanceRequest.date.desc()).limit(8).all()) if room_ids else []
        from utils import equipment_rates
        rates = equipment_rates(room_ids)
        return render_template("dashboard_chef_travaux.html", stats=stats, recent_maintenance=recent_maintenance, rates=rates)

    if role == "enseignant":
        teacher = user.teacher_profile
        courses = teacher.courses if teacher else []
        my_schedule = ScheduleEntry.query.join(Course).filter(Course.teacher_id == teacher.id).all() if teacher else []
        return render_template("dashboard_enseignant.html", teacher=teacher, courses=courses,
                                schedule=my_schedule)

    if role == "eleve":
        student = user.student_profile
        avg = general_average(student.id) if student else None
        recent_grades = Grade.query.filter_by(student_id=student.id).order_by(Grade.date.desc()).limit(6).all() if student else []
        announcements = Announcement.query.filter(Announcement.target_role.in_(["tous", "eleve"])).order_by(Announcement.date.desc()).limit(5).all()
        return render_template("dashboard_eleve.html", student=student, avg=avg,
                                recent_grades=recent_grades, announcements=announcements)

    if role == "parent":
        parent = user.parent_profile
        children = parent.children if parent else []
        child_data = [(c, general_average(c.id)) for c in children]
        announcements = Announcement.query.filter(Announcement.target_role.in_(["tous", "parent"])).order_by(Announcement.date.desc()).limit(5).all()
        return render_template("dashboard_parent.html", child_data=child_data, announcements=announcements)

    abort(403)


# ----------------------------------------------------------------- profil ---
@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    user = User.query.get(session["user_id"])
    if request.method == "POST":
        user.email = request.form.get("email", user.email)
        user.phone = request.form.get("phone", user.phone)
        new_pw = request.form.get("new_password")
        if new_pw:
            user.set_password(new_pw)
            flash("Mot de passe mis à jour.", "success")
        db.session.commit()
        flash("Profil mis à jour.", "success")
        return redirect(url_for("profil"))
    return render_template("profil.html", user=user)


# --------------------------------------------------------------- messages ---
@app.route("/messages")
@login_required
def messages_inbox():
    uid = session["user_id"]
    box = request.args.get("box", "reception")
    if box == "envois":
        msgs = Message.query.filter_by(sender_id=uid).order_by(Message.date.desc()).all()
    else:
        msgs = Message.query.filter_by(recipient_id=uid).order_by(Message.date.desc()).all()
    return render_template("messages.html", msgs=msgs, box=box)


@app.route("/messages/nouveau", methods=["GET", "POST"])
@login_required
def messages_new():
    user = User.query.get(session["user_id"])
    # Destinataires autorisés selon le rôle
    role = user.role
    if role in ("directeur", "censeur"):
        candidates = User.query.filter(User.id != user.id).order_by(User.role, User.full_name).all()
    elif role == "enseignant":
        candidates = User.query.filter(User.role.in_(["directeur", "censeur", "eleve", "parent"])).order_by(User.role, User.full_name).all()
    elif role == "eleve":
        candidates = User.query.filter(User.role.in_(["directeur", "censeur", "enseignant"])).order_by(User.role, User.full_name).all()
    else:  # parent
        candidates = User.query.filter(User.role.in_(["directeur", "censeur", "enseignant"])).order_by(User.role, User.full_name).all()

    prefill_to = request.args.get("to", type=int)

    if request.method == "POST":
        recipient_id = request.form.get("recipient_id", type=int)
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        if not (recipient_id and subject and body):
            flash("Veuillez remplir tous les champs.", "warning")
        else:
            db.session.add(Message(sender_id=user.id, recipient_id=recipient_id, subject=subject, body=body))
            notify(recipient_id, f"Nouveau message de {user.full_name} : {subject}", link=url_for("messages_inbox"))
            db.session.commit()
            flash("Message envoyé.", "success")
            return redirect(url_for("messages_inbox"))
    return render_template("message_new.html", candidates=candidates, prefill_to=prefill_to)


@app.route("/messages/<int:msg_id>")
@login_required
def message_view(msg_id):
    msg = Message.query.get_or_404(msg_id)
    uid = session["user_id"]
    if uid not in (msg.sender_id, msg.recipient_id):
        abort(403)
    if msg.recipient_id == uid and not msg.read:
        msg.read = True
        db.session.commit()
    return render_template("message_view.html", msg=msg)


# ------------------------------------------------------------ annonces ---
@app.route("/annonces", methods=["GET", "POST"])
@login_required
def announcements():
    user = User.query.get(session["user_id"])
    if request.method == "POST" and user.role in ("directeur", "censeur"):
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        target = request.form.get("target_role", "tous")
        if title and body:
            db.session.add(Announcement(title=title, body=body, author_id=user.id, target_role=target))
            db.session.commit()
            flash("Annonce publiée.", "success")
        return redirect(url_for("announcements"))

    if user.role in ("directeur", "censeur"):
        items = Announcement.query.order_by(Announcement.date.desc()).all()
    else:
        items = Announcement.query.filter(Announcement.target_role.in_(["tous", user.role])).order_by(Announcement.date.desc()).all()
    return render_template("announcements.html", items=items)


@app.route("/notifications/lu/<int:notif_id>")
@login_required
def notif_read(notif_id):
    n = Notification.query.get_or_404(notif_id)
    if n.user_id != session["user_id"]:
        abort(403)
    n.read = True
    db.session.commit()
    return redirect(n.link or url_for("dashboard"))


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Accès refusé — vous n'avez pas la permission d'accéder à cette page."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page introuvable."), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template("error.html", code=500, message="Une erreur inattendue est survenue. Réessayez ou contactez l'administration."), 500

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "ltt", "environment": app.config["ENVIRONMENT"]})

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

# Enregistrement des routes par rôle (importées après la création de `app`
# pour éviter les imports circulaires).
import directeur_routes   # noqa: E402,F401
import censeur_routes     # noqa: E402,F401
import enseignant_routes  # noqa: E402,F401
import eleve_routes       # noqa: E402,F401
import parent_routes      # noqa: E402,F401
import import_routes      # noqa: E402,F401
import life_school_routes # noqa: E402,F401
import evaluation_routes  # noqa: E402,F401
