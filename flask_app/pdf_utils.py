import os
import base64
import hashlib
import logging
import mimetypes
from io import BytesIO
from urllib.request import urlopen
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
    if os.getenv("LTT_ENV") == "production":
        return f"http://127.0.0.1:{os.getenv('PORT', '3000')}"
    configured = os.getenv("LTT_STORAGE_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    if has_request_context():
        return request.host_url.rstrip("/")
    return ""


def pdf_asset(local_parts, storage_path, base_url=None):
    # Les photos élèves sont stockées sous /manus-storage/students/ et doivent
    # être récupérées même hors du mode production lors d’un aperçu PDF local.
    should_fetch = os.getenv("LTT_ENV") == "production" or storage_path.startswith("/manus-storage/students/")
    fetch_base = (base_url or storage_base_url()).rstrip("/")
    if should_fetch and fetch_base:
        cache_dir = "/tmp/ltt-pdf-assets"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, os.path.basename(storage_path))
        if not os.path.exists(cache_path):
            try:
                with urlopen(f"{fetch_base}{storage_path}", timeout=15) as response:
                    with open(cache_path, "wb") as output:
                        output.write(response.read())
            except Exception:
                pass
        if os.path.isfile(cache_path):
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
        cache_dir = "/tmp/ltt-pdf-assets/raw-students"
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
        cache_dir = "/tmp/ltt-pdf-assets"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, os.path.basename(value.split("?", 1)[0]))
        if not os.path.exists(cache_path):
            try:
                with urlopen(value, timeout=10) as response:
                    with open(cache_path, "wb") as output:
                        output.write(response.read())
            except Exception:
                return None
        path = cache_path if os.path.exists(cache_path) else None
        return path if path and os.path.isfile(path) else None
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
    cache_dir = "/tmp/ltt-pdf-assets/lightweight-students"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, os.path.splitext(os.path.basename(source_path))[0] + ".jpg")
    try:
        source_mtime = os.path.getmtime(source_path)
        if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
            with Image.open(cache_path) as cached:
                cached.verify()
            return cache_path
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.load()
            image = image.convert("RGB")
            if lightweight:
                image.thumbnail((320, 400), Image.Resampling.LANCZOS)
            else:
                image.thumbnail((1200, 1600), Image.Resampling.LANCZOS)
            image.save(cache_path, format="JPEG", quality=85, optimize=True)
        with Image.open(cache_path) as converted:
            converted.verify()
        return cache_path
    except Exception:
        return None


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
    try:
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
