"""Ajout du QR à la page finalisée, sans modifier les données du bulletin.

Un espace blanc est réservé en bas si nécessaire ; la page existante est
uniformément ajustée pour ne masquer ni appréciations ni visas.
"""
from io import BytesIO

import qrcode
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from bulletin_qr import build_bulletin_qr_url

QR_SIZE = 60.0
QR_MARGIN = 13.5
QR_CLEARANCE = 6.0
BULLETIN_TEMPLATES = {
    'pdf/bulletin_pdf.html', 'pdf/class_bulletins_pdf.html',
    'pdf/bulletin_annual_pdf.html', 'pdf/class_annual_bulletins_pdf.html',
}


def _multiply(a, b):
    """Composition affine suivant l'ordre du flux PDF (nouvelle * courante)."""
    return (a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3],
            a[2]*b[0]+a[3]*b[2], a[2]*b[1]+a[3]*b[3],
            a[4]*b[0]+a[5]*b[2]+b[4], a[4]*b[1]+a[5]*b[3]+b[5])


def _content_bottom(page):
    """Mesure les bords des cadres, images et textes, en points PDF."""
    ys = []
    current = (1., 0., 0., 1., 0., 0.)
    stack = []
    xobjects = page['/Resources'].get('/XObject', {})
    if hasattr(xobjects, 'get_object'):
        xobjects = xobjects.get_object()

    def add_point(x, y):
        ys.append(current[1]*float(x)+current[3]*float(y)+current[5])

    for args, op in page.get_contents().operations:
        if op == b'q':
            stack.append(current)
        elif op == b'Q':
            current = stack.pop() if stack else (1., 0., 0., 1., 0., 0.)
        elif op == b'cm':
            current = _multiply(tuple(float(v) for v in args), current)
        elif op == b're':
            x, y, w, h = [float(v) for v in args]
            for px, py in ((x,y), (x+w,y), (x,y+h), (x+w,y+h)):
                add_point(px, py)
        elif op in (b'm', b'l'):
            add_point(args[0], args[1])
        elif op == b'c':
            for i in (0,2,4):
                add_point(args[i], args[i+1])
        elif op == b'Do':
            resource = xobjects.get(args[0])
            if resource and resource.get_object().get('/Subtype') == '/Image':
                for px, py in ((0,0),(1,0),(0,1),(1,1)):
                    add_point(px,py)

    def visitor(text, cm, tm, font, size):
        if text.strip():
            matrix = _multiply(tm, cm)
            ys.append(matrix[5] - abs(float(size))*.3)

    page.extract_text(visitor_text=visitor)
    return max(0., min(ys)-1.) if ys else QR_MARGIN


def add_bulletin_qr_codes(pdf_buffer, rows, school_year, term):
    reader = PdfReader(pdf_buffer)
    rows = [row for row in rows if row.get('data')]
    # En cas de débordement, le renderer groupé réessaiera élève par élève :
    # aucune page n'est associée au mauvais élève par décalage d'index.
    if len(reader.pages) != len(rows):
        raise ValueError('Chaque QR exige exactement une page par élève')
    writer = PdfWriter()
    if reader.metadata:
        writer.add_metadata(reader.metadata)
    for page, row in zip(reader.pages, rows):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        bottom = _content_bottom(page)
        required = QR_MARGIN + QR_SIZE + QR_CLEARANCE
        if bottom < required:
            scale = (height-required)/(height-bottom)
            page.add_transformation(Transformation().scale(scale).translate(
                tx=QR_MARGIN*(1-scale), ty=height*(1-scale)))
        url = build_bulletin_qr_url(row['student'], row['data'], school_year=school_year, term=term)
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(fill_color='black', back_color='white').convert('RGB')
        overlay = BytesIO()
        drawing = canvas.Canvas(overlay, pagesize=(width, height), pageCompression=1)
        drawing.drawImage(ImageReader(image), QR_MARGIN, QR_MARGIN, width=QR_SIZE, height=QR_SIZE)
        drawing.linkURL(url, (QR_MARGIN, QR_MARGIN, QR_MARGIN+QR_SIZE, QR_MARGIN+QR_SIZE), thickness=0)
        drawing.save()
        overlay.seek(0)
        page.merge_page(PdfReader(overlay).pages[0])
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output
