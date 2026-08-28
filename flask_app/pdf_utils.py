import os
import os
from io import BytesIO
from urllib.request import urlopen
from flask import render_template
from xhtml2pdf import pisa

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


def student_photo_pdf_path(photo):
    """Retourne un chemin local utilisable par xhtml2pdf pour une photo élève."""
    if not photo:
        return None
    if photo.startswith("/manus-storage/"):
        return pdf_asset(("img", "avatar_placeholder.png"), photo)
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
        return cache_path if os.path.exists(cache_path) else None
    local_path = asset_path("uploads", "students", os.path.basename(photo))
    return local_path if os.path.exists(local_path) else None


def render_pdf(template_name, **context):
    """Rend un template Jinja dédié à l'impression en PDF et renvoie un flux binaire (BytesIO)."""
    context.setdefault("logo_path", pdf_asset(("img", "logo.png"), "/manus-storage/logo_10e20177.png"))
    context.setdefault("avatar_path", pdf_asset(("img", "avatar_placeholder.png"), "/manus-storage/avatar_placeholder_42973e92.png"))
    context.setdefault("student_photo_dir", asset_path("uploads", "students"))
    context.setdefault("font_bold", pdf_asset(("vendor", "fonts", "PlayfairDisplay-Bold.ttf"), "/manus-storage/PlayfairDisplay-Bold_a8c270a5.ttf"))
    context.setdefault("font_regular", pdf_asset(("vendor", "fonts", "Inter-Variable.ttf"), "/manus-storage/Inter-Variable_d79f128a.ttf"))
    context.setdefault("storage_base_url", storage_base_url())
    html = render_template(template_name, **context)
    buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=buffer)
    buffer.seek(0)
    if result.err:
        return None
    return buffer
