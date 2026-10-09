import os
import base64
from io import BytesIO
from urllib.request import urlopen
from flask import render_template
from xhtml2pdf import pisa
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def asset_path(*parts):
    """Chemin absolu vers un asset de rendu PDF, hors ressources lourdes du conteneur."""
    return os.path.join(os.getenv("LTT_PDF_ASSET_ROOT", "/home/ubuntu/webdev-static-assets/ltt"), *parts)


def storage_base_url():
    if os.getenv("LTT_ENV") == "production":
        return f"http://127.0.0.1:{os.getenv('PORT', '3000')}"
    return ""


def pdf_asset(local_parts, storage_path):
    if os.getenv("LTT_ENV") == "production":
        cache_dir = "/tmp/ltt-pdf-assets"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, os.path.basename(storage_path))
        if not os.path.exists(cache_path):
            try:
                with urlopen(f"{storage_base_url()}{storage_path}", timeout=10) as response:
                    with open(cache_path, "wb") as output:
                        output.write(response.read())
            except Exception:
                return asset_path(*local_parts)
        return cache_path
    return asset_path(*local_parts)


def pdf_image_data_uri(path, mime_type="image/png"):
    """Retourne une image locale sous forme de données embarquées pour xhtml2pdf."""
    if not path or not os.path.isfile(path):
        return path
    try:
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
    except OSError:
        return path


def student_photo_pdf_path(photo, lightweight=False):
    """Retourne un chemin local utilisable par xhtml2pdf pour une photo élève."""
    if not photo:
        return None
    if photo.startswith("/manus-storage/"):
        path = pdf_asset(("img", "avatar_placeholder.png"), photo)
        return _lightweight_photo_path(path) if lightweight and path else path
    if photo.startswith(("http://", "https://")):
        cache_dir = "/tmp/ltt-pdf-assets"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, os.path.basename(photo.split("?", 1)[0]))
        if not os.path.exists(cache_path):
            try:
                with urlopen(photo, timeout=10) as response:
                    with open(cache_path, "wb") as output:
                        output.write(response.read())
            except Exception:
                return None
        path = cache_path if os.path.exists(cache_path) else None
        return _lightweight_photo_path(path) if lightweight and path else path
    local_path = asset_path("uploads", "students", os.path.basename(photo))
    if not os.path.exists(local_path):
        return None
    if not lightweight:
        return local_path
    return _lightweight_photo_path(local_path)


def _lightweight_photo_path(source_path):
    """Crée une vignette JPEG réutilisable pour les PDF groupés."""
    cache_dir = "/tmp/ltt-pdf-assets/lightweight-students"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, os.path.splitext(os.path.basename(source_path))[0] + ".jpg")
    try:
        source_mtime = os.path.getmtime(source_path)
        if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
            return cache_path
        with Image.open(source_path) as image:
            image = image.convert("RGB")
            image.thumbnail((320, 400), Image.Resampling.LANCZOS)
            image.save(cache_path, format="JPEG", quality=72, optimize=True)
        return cache_path
    except Exception:
        return source_path


def render_pdf(template_name, **context):
    """Rend un template Jinja dédié à l'impression en PDF et renvoie un flux binaire (BytesIO)."""
    logo_path = pdf_asset(("img", "bulletin_official_logo.png"), "/manus-storage/LOGOLTT_b9c57b93.jpg")
    embedded_logo = pdf_image_data_uri(logo_path)
    context.setdefault("logo_path", embedded_logo)
    context.setdefault("bulletin_logo_path", embedded_logo)
    context.setdefault("avatar_path", pdf_asset(("img", "avatar_placeholder.png"), "/manus-storage/avatar_placeholder_42973e92.png"))
    context.setdefault("student_photo_dir", asset_path("uploads", "students"))
    context.setdefault("font_bold", pdf_asset(("vendor", "fonts", "PlayfairDisplay-Bold.ttf"), "/manus-storage/PlayfairDisplay-Bold_a8c270a5.ttf"))
    context.setdefault("font_regular", pdf_asset(("vendor", "fonts", "Inter-Variable.ttf"), "/manus-storage/Inter-Variable_d79f128a.ttf"))
    context.setdefault("bulletin_serif_regular", pdf_asset(("fonts", "LiberationSerif-Regular.ttf"), "/manus-storage/LiberationSerif-Regular_78c6f770.ttf"))
    context.setdefault("bulletin_serif_bold", pdf_asset(("fonts", "LiberationSerif-Bold.ttf"), "/manus-storage/LiberationSerif-Bold_93dca24b.ttf"))
    context.setdefault("bulletin_serif_italic", pdf_asset(("fonts", "LiberationSerif-Italic.ttf"), "/manus-storage/LiberationSerif-Italic_df811de7.ttf"))
    context.setdefault("bulletin_sans_regular", pdf_asset(("fonts", "LiberationSans-Regular.ttf"), "/manus-storage/LiberationSans-Regular_e967eb0a.ttf"))
    context.setdefault("storage_base_url", storage_base_url())
    html = render_template(template_name, **context)
    buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=buffer)
    buffer.seek(0)
    if result.err:
        return None
    return buffer
