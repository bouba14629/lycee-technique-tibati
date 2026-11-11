import os
import base64
import hashlib
import logging
import mimetypes
import tempfile
from io import BytesIO
from urllib.request import urlopen
from urllib.parse import urlsplit
from flask import render_template, has_request_context, request
from xhtml2pdf import pisa
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)


def asset_path(*parts):
    """Chemin absolu vers un asset de rendu PDF, hors ressources lourdes du conteneur."""
    return os.path.join(os.getenv("LTT_PDF_ASSET_ROOT", "/home/ubuntu/webdev-static-assets/ltt"), *parts)


def bulletin_logo_pdf_path():
    """Retourne le logo embarqué, prioritaire sur toute ressource distante."""
    packaged = os.path.join(BASE_DIR, "templates", "pdf", "bulletin_model", "LOGOLTT.jpg")
    if os.path.isfile(packaged):
        return packaged
    return asset_path("img", "bulletin_official_logo.png")


def storage_base_url():
    configured = os.getenv("LTT_STORAGE_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    if os.getenv("LTT_ENV") == "production" or os.getenv("NODE_ENV") == "production":
        return f"http://127.0.0.1:{os.getenv('PORT', '3000')}"
    if has_request_context():
        host = urlsplit(request.host_url)
        if host.hostname in {"127.0.0.1", "localhost"} and host.port == int(os.getenv("LTT_PORT", "5053")):
            return f"http://127.0.0.1:{os.getenv('PORT', '3000')}"
        return request.host_url.rstrip("/")
    return ""


def _pdf_cache_dir(*parts):
    return os.path.join(os.getenv("LTT_PDF_CACHE_ROOT", "/tmp/ltt-pdf-assets"), *parts)


def _download_pdf_asset(url):
    """Cache par URL complète ; un téléchargement partiel n'est jamais publié."""
    cache_dir = _pdf_cache_dir("downloads-v2")
    os.makedirs(cache_dir, exist_ok=True)
    suffix = os.path.splitext(urlsplit(url).path)[1][:12]
    cache_path = os.path.join(cache_dir, hashlib.sha256(url.encode()).hexdigest() + suffix)
    if os.path.isfile(cache_path) and os.path.getsize(cache_path):
        return cache_path
    temp_path = None
    try:
        with urlopen(url, timeout=10) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if not raw or len(raw) > 16 * 1024 * 1024:
            return None
        with tempfile.NamedTemporaryFile(dir=cache_dir, delete=False) as output:
            temp_path = output.name
            output.write(raw)
        os.replace(temp_path, cache_path)
        return cache_path
    except Exception:
        logger.warning("PDF asset download failed host=%s", urlsplit(url).netloc, exc_info=True)
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def pdf_asset(local_parts, storage_path, base_url=None):
    # Les photos élèves sont stockées sous /manus-storage/students/ et doivent
    # être récupérées même hors du mode production lors d’un aperçu PDF local.
    local_path = asset_path(*local_parts)
    is_student_photo = storage_path.startswith("/manus-storage/students/")
    if not is_student_photo and os.path.isfile(local_path):
        return local_path
    should_fetch = os.getenv("LTT_ENV") == "production" or os.getenv("NODE_ENV") == "production" or is_student_photo
    # L'adresse configurée de Node prime sur request.host_url (port Flask).
    fetch_base = (storage_base_url() or base_url or "").rstrip("/")
    if should_fetch and fetch_base:
        cache_path = _download_pdf_asset(f"{fetch_base}{storage_path}")
        if cache_path:
            return cache_path
    return asset_path(*local_parts)


def pdf_image_data_uri(path, mime_type=None):
    """Retourne une image locale sous forme de données embarquées pour xhtml2pdf."""
    if not path or not os.path.isfile(path):
        return path
    try:
        mime_type = mime_type or mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
    except OSError:
        return path


def _photo_value_to_local_path(photo, base_url=None):
    """Convertit toute forme de valeur photo en fichier local lisible."""
    if not photo:
        return None
    if isinstance(photo, (bytes, bytearray)):
        raw = bytes(photo)
        source_name = "binary-" + hashlib.sha256(raw).hexdigest()[:24]
        cache_dir = _pdf_cache_dir("raw-students")
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, source_name)
        if not os.path.isfile(path):
            with open(path, "wb") as output:
                output.write(raw)
        return path
    if hasattr(photo, "read"):
        try:
            position = photo.tell()
        except Exception:
            position = None
        try:
            raw = photo.read()
        finally:
            if position is not None:
                try:
                    photo.seek(position)
                except Exception:
                    pass
        return _photo_value_to_local_path(raw, base_url=base_url)
    value = str(photo).strip()
    if not value:
        return None
    if value.startswith("/manus-storage/"):
        path = pdf_asset(("img", "avatar_placeholder.png"), value, base_url=base_url)
        # pdf_asset utilise l’avatar comme repli ; il ne doit jamais être
        # considéré comme la photo réelle de l’élève.
        if path == asset_path("img", "avatar_placeholder.png"):
            return None
        return path if path and os.path.isfile(path) else None
    if value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        if parsed.path.startswith("/manus-storage/"):
            return _photo_value_to_local_path(parsed.path, base_url=base_url)
        return _download_pdf_asset(value)
    candidate = value
    if candidate.startswith("static/"):
        candidate = candidate[len("static/"):]
    if candidate.startswith("/static/"):
        candidate = candidate[len("/static/"):]
    if os.path.isabs(candidate) and os.path.isfile(candidate):
        return candidate
    if candidate.startswith("uploads/students/"):
        return asset_path(*candidate.split("/")) if os.path.isfile(asset_path(*candidate.split("/"))) else None
    local_path = asset_path("uploads", "students", os.path.basename(candidate))
    return local_path if os.path.isfile(local_path) else None


def resolve_student_photo(student, lightweight=True, base_url=None):
    """Résout Student.photo et retourne un chemin local prêt pour le PDF.

    Le diagnostic est volontairement détaillé dans les logs afin de suivre chaque
    élève dans un export groupé sans exposer ces informations dans le bulletin.
    """
    raw = getattr(student, "photo", None)
    try:
        source_path = _photo_value_to_local_path(raw, base_url=base_url)
        final_path = _lightweight_photo_path(source_path, lightweight=lightweight) if source_path else None
    except Exception:
        logger.exception("Student photo resolution failed id=%s", getattr(student, "id", None))
        source_path = None
        final_path = None
    image_format = None
    size = None
    if final_path and os.path.isfile(final_path):
        size = os.path.getsize(final_path)
        try:
            with Image.open(final_path) as image:
                image_format = image.format
        except Exception:
            final_path = None
    logger.info(
        "Student photo diagnostic id=%s raw=%r type=%s final=%r exists=%s size=%s format=%s",
        getattr(student, "id", None), raw, type(raw).__name__, final_path,
        bool(final_path and os.path.isfile(final_path)), size, image_format,
    )
    return final_path


def get_student_photo_source(student, base_url=None):
    """Retourne une source HTML/PDF autonome pour la photo de cet élève.

    ``Student.photo`` est actuellement une chaîne (chemin ``/manus-storage``
    ou nom de fichier), mais la résolution accepte aussi les fichiers et les
    octets. La conversion en data URI évite que xhtml2pdf perde le fichier
    local lorsque plusieurs bulletins sont rendus dans un même PDF.
    """
    try:
        local_path = resolve_student_photo(student, lightweight=True, base_url=base_url)
        return pdf_image_data_uri(local_path) if local_path else None
    except Exception:
        logger.exception("Student photo source creation failed id=%s", getattr(student, "id", None))
        return None


def student_photo_pdf_path(photo, lightweight=False, base_url=None):
    """Compatibilité historique : résout directement une valeur photo."""
    class PhotoHolder:
        pass
    holder = PhotoHolder()
    holder.id = None
    holder.photo = photo
    return resolve_student_photo(holder, lightweight=lightweight, base_url=base_url)


def _lightweight_photo_path(source_path, lightweight=True):
    """Valide et convertit une photo en JPEG RGB lisible par xhtml2pdf."""
    cache_dir = _pdf_cache_dir("lightweight-students-v2")
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = hashlib.sha256(f"{os.path.realpath(source_path)}:{lightweight}".encode()).hexdigest()
    cache_path = os.path.join(cache_dir, cache_key + ".jpg")
    temp_path = None
    try:
        source_mtime = os.path.getmtime(source_path)
        if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
            try:
                with Image.open(cache_path) as cached:
                    cached.verify()
                return cache_path
            except Exception:
                os.unlink(cache_path)
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.load()
            image = image.convert("RGB")
            if lightweight:
                image.thumbnail((320, 400), Image.Resampling.LANCZOS)
            else:
                image.thumbnail((1200, 1600), Image.Resampling.LANCZOS)
            with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".jpg", delete=False) as output:
                temp_path = output.name
            image.save(temp_path, format="JPEG", quality=85, optimize=True)
        with Image.open(temp_path) as converted:
            converted.verify()
        os.replace(temp_path, cache_path)
        return cache_path
    except Exception:
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def select_student_photo_for_pdf(photo, fallback_path, base_url=None):
    """Choisit automatiquement la stratégie de rendu la plus fiable.

    Une photo réelle est validée/convertie par Pillow, embarquée dans le HTML
    et conservée pour l’incrustation directe après le rendu PDF. Si elle est
    absente ou illisible, seul le cadre de secours est conservé.
    """
    actual_path = student_photo_pdf_path(photo, lightweight=True, base_url=base_url)
    return {
        "path": actual_path or fallback_path,
        "overlay_path": actual_path,
        "available": bool(actual_path),
        "method": "html-and-direct-overlay" if actual_path else "placeholder-frame",
    }


def render_pdf(template_name, **context):
    """Rend un template Jinja dédié à l'impression en PDF et renvoie un flux binaire (BytesIO)."""
    logo_path = bulletin_logo_pdf_path()
    embedded_logo = pdf_image_data_uri(logo_path)
    context.setdefault("logo_path", embedded_logo)
    context.setdefault("bulletin_logo_path", embedded_logo)
    avatar_path = pdf_asset(("img", "avatar_placeholder.png"), "/manus-storage/avatar_placeholder_42973e92.png")
    context.setdefault("avatar_path", pdf_image_data_uri(avatar_path))
    context.setdefault("student_photo_dir", asset_path("uploads", "students"))
    context.setdefault("font_bold", pdf_asset(("vendor", "fonts", "PlayfairDisplay-Bold.ttf"), "/manus-storage/PlayfairDisplay-Bold_a8c270a5.ttf"))
    context.setdefault("font_regular", pdf_asset(("vendor", "fonts", "Inter-Variable.ttf"), "/manus-storage/Inter-Variable_d79f128a.ttf"))
    context.setdefault("bulletin_serif_regular", pdf_asset(("fonts", "LiberationSerif-Regular.ttf"), "/manus-storage/LiberationSerif-Regular_78c6f770.ttf"))
    context.setdefault("bulletin_serif_bold", pdf_asset(("fonts", "LiberationSerif-Bold.ttf"), "/manus-storage/LiberationSerif-Bold_93dca24b.ttf"))
    context.setdefault("bulletin_serif_italic", pdf_asset(("fonts", "LiberationSerif-Italic.ttf"), "/manus-storage/LiberationSerif-Italic_df811de7.ttf"))
    context.setdefault("bulletin_sans_regular", pdf_asset(("fonts", "LiberationSans-Regular.ttf"), "/manus-storage/LiberationSans-Regular_e967eb0a.ttf"))
    context.setdefault("storage_base_url", storage_base_url())
    if template_name in ("pdf/bulletin_annual_pdf.html", "pdf/class_annual_bulletins_pdf.html"):
        context.setdefault("annual_sans_regular", pdf_asset(("fonts", "LiberationSans-Regular.ttf"), "/manus-storage/LiberationSans-Regular_4bbc26b5.ttf"))
        context.setdefault("annual_sans_bold", pdf_asset(("fonts", "LiberationSans-Bold.ttf"), "/manus-storage/LiberationSans-Bold_62710961.ttf"))
        context.setdefault("annual_sans_bold_italic", pdf_asset(("fonts", "LiberationSans-BoldItalic.ttf"), "/manus-storage/LiberationSans-BoldItalic_1aa70013.ttf"))
        context.setdefault("annual_logo_path", pdf_image_data_uri(pdf_asset(("img", "annual_reference_logo.jpeg"), "/manus-storage/annual_reference_logo_8d168140.jpeg")))
    try:
        if template_name in ("pdf/bulletin_annual_pdf.html", "pdf/class_annual_bulletins_pdf.html"):
            from annual_pdf import render_annual_bulletins_pdf
            return render_annual_bulletins_pdf(**context)
        html = render_template(template_name, **context)
        buffer = BytesIO()
        result = pisa.CreatePDF(html, dest=buffer, link_callback=_pdf_link_callback)
        buffer.seek(0)
        if result.err:
            logger.error("PDF rendering reported errors template=%s errors=%s", template_name, result.err)
            return None
        return buffer
    except Exception:
        logger.exception("PDF rendering failed template=%s", template_name)
        return None


def render_grouped_bulletins_pdf(template_name, students_data, **context):
    """Rendu groupé, puis assemblage individuel identique si nécessaire.

    Le secours conserve exactement les sources photo, données et template.
    Aucun PDF incomplet ou sans les photos valides n'est retourné.
    """
    pdf = render_pdf(template_name, students_data=students_data, **context)
    if pdf:
        return pdf
    try:
        writer = PdfWriter()
        for row in students_data:
            individual = render_pdf(template_name, students_data=[row], **context)
            if not individual:
                return None
            writer.append(PdfReader(individual))
        if not writer.pages:
            return None
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        return output
    except Exception:
        logger.exception("Grouped bulletin assembly failed template=%s", template_name)
        return None


def _pdf_link_callback(uri, rel):
    """Permet à xhtml2pdf de lire les chemins locaux transmis aux balises img."""
    if not uri or uri.startswith("data:"):
        return uri
    if os.path.isfile(uri):
        return uri
    if uri.startswith("file://") and os.path.isfile(uri[7:]):
        return uri[7:]
    return uri


def overlay_student_photos(pdf_buffer, photo_paths):
    """Incruste les photos validées sur les pages correspondantes du PDF."""
    if not pdf_buffer or not photo_paths:
        return pdf_buffer
    try:
        reader = PdfReader(pdf_buffer)
        writer = PdfWriter()
        for index, page in enumerate(reader.pages):
            photo_path = photo_paths[index] if index < len(photo_paths) else None
            if photo_path and os.path.isfile(photo_path):
                try:
                    overlay_stream = BytesIO()
                    canvas_pdf = canvas.Canvas(overlay_stream, pagesize=(595.28, 841.89))
                    # Coordonnées fixes du cadre photo du bulletin A4 groupé,
                    # alignées sur le modèle importé : à droite du bloc identité.
                    x, y, width, height = 527, 624, 50, 60
                    canvas_pdf.setFillColorRGB(1, 1, 1)
                    canvas_pdf.rect(x, y, width, height, fill=1, stroke=0)
                    canvas_pdf.drawImage(
                        ImageReader(photo_path), x + 2, y + 2, width=46, height=56,
                        preserveAspectRatio=True, anchor="c", mask="auto",
                    )
                    canvas_pdf.setStrokeColorRGB(0, 0, 0)
                    canvas_pdf.setLineWidth(1.1)
                    canvas_pdf.rect(x, y, width, height, fill=0, stroke=1)
                    canvas_pdf.save()
                    overlay_stream.seek(0)
                    page.merge_page(PdfReader(overlay_stream).pages[0])
                except Exception:
                    # Une photo corrompue ne doit pas empêcher les autres
                    # élèves de recevoir leur photo dans le même PDF.
                    pass
            writer.add_page(page)
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        return output
    except Exception:
        return pdf_buffer
