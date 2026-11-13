"""Modèle annuel importé : dessin vectoriel mesuré, données fournies par annual_bulletin_data.

Aucune note n'est calculée/modifiée ici. Les mêmes pages servent l'individuel et le groupé.
Les coordonnées, polices, bordures et zones grises proviennent du modèle du 21 octobre.
"""
import base64
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

LOGGER = logging.getLogger(__name__)
PAGE_W, PAGE_H = 595.92, 842.88
LEFT, RIGHT = 13.5, 582.0
GRAY = colors.HexColor('#d3d3d3')
BLUE = colors.HexColor('#14274e')
RED = colors.HexColor('#c00000')
BLACK = colors.black
COLUMN_EDGES = [13.5, 212.25, 258.0, 293.25, 328.5, 363.75, 392.25, 427.5, 457.5, 582.0]


def _fonts(context):
    result = {}
    for kind, key, fallback in [('normal', 'annual_sans_regular', 'Helvetica'),
                                ('bold', 'annual_sans_bold', 'Helvetica-Bold'),
                                ('italic', 'annual_sans_bold_italic', 'Helvetica-BoldOblique')]:
        path = context.get(key)
        name = 'AnnualImported-' + kind
        if path and Path(path).is_file():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, path))
            result[kind] = name
        else:
            LOGGER.warning('Annual model font unavailable kind=%s; using %s', kind, fallback)
            result[kind] = fallback
    return result


def _image(source, portrait=False):
    if not source:
        return None
    try:
        raw = BytesIO(base64.b64decode(source.split(',', 1)[1])) if str(source).startswith('data:') else source
        with Image.open(raw) as im:
            im = ImageOps.exif_transpose(im).convert('RGB')
            if portrait:
                # Proportions du cadre importé ; recadrage centré plutôt que déformation.
                im = ImageOps.fit(im, (264, 296), Image.Resampling.LANCZOS)
            return ImageReader(im.copy())
    except Exception:
        LOGGER.warning('Annual model image invalid; retaining other students photos', exc_info=True)
        return None


def _value(value):
    return '—' if value is None else str(value)


def _color(value):
    return RED if value is not None and isinstance(value, (int, float)) and value < 10 else BLACK


class AnnualPage:
    def __init__(self, pdf, fonts):
        self.pdf = pdf
        self.fonts = fonts

    def text(self, text, x, top, size=6.9, kind='bold', color=BLACK, align='left', max_width=None, char_space=0):
        font = self.fonts[kind]
        text = str(text)
        if max_width and pdfmetrics.stringWidth(text, font, size) > max_width:
            # Les longues matières se réduisent déjà à 6,225 pt dans le modèle fourni.
            size = min(size, max_width * size / pdfmetrics.stringWidth(text, font, size))
        self.pdf.setFont(font, size)
        self.pdf.setFillColor(color)
        y = PAGE_H - top
        if char_space:
            width = pdfmetrics.stringWidth(text, font, size) + max(0, len(text)-1)*char_space
            if align == 'center':
                x -= width/2
            elif align == 'right':
                x -= width
            cursor = self.pdf.beginText(x, y)
            cursor.setFont(font, size)
            cursor.setCharSpace(char_space)
            cursor.textOut(text)
            cursor.setCharSpace(0)
            self.pdf.drawText(cursor)
        elif align == 'center':
            self.pdf.drawCentredString(x, y, text)
        elif align == 'right':
            self.pdf.drawRightString(x, y, text)
        else:
            self.pdf.drawString(x, y, text)

    def box(self, x0, x1, top, height, fill=None):
        self.pdf.setLineWidth(.75)
        self.pdf.setStrokeColor(BLACK)
        self.pdf.setFillColor(fill or colors.white)
        self.pdf.rect(x0, PAGE_H - top - height, x1 - x0, height, stroke=1, fill=1)

    def bar(self, top):
        self.pdf.setFillColor(BLACK)
        self.pdf.rect(LEFT, PAGE_H - top - 2.25, RIGHT - LEFT, 2.25, fill=1, stroke=0)

    def row(self, top, height, edges, texts, fill=None, center_columns=(), colors_by_column=None, size=6.9):
        for i, (x0, x1) in enumerate(zip(edges, edges[1:])):
            self.box(x0, x1, top, height, fill)
            text = texts[i] if i < len(texts) else ''
            center = i in center_columns
            color = (colors_by_column or {}).get(i, BLACK)
            baseline = top + height / 2 + size * .34
            self.text(text, (x0 + x1) / 2 if center else x0 + 3, baseline,
                      size=size, color=color, align='center' if center else 'left', max_width=x1-x0-6)

    def header(self, student, data, context):
        left_lines = ['RÉPUBLIQUE DU CAMEROUN', 'Paix – Travail – Patrie', "RÉGION DE L'ADAMAOUA",
                      'DDRES/DDES-DJEREM', 'LYCÉE TECHNIQUE DE TIBATI', 'Mle : 2CE1TEFD110320092']
        right_lines = ['REPUBLIC OF CAMEROON', 'Peace – Work – Fatherland', 'ADAMAWA REGION',
                       'RDSE/DDES-DJEREM', 'G.T.H.S OF TIBATI', 'Mle : 2CE1TEFD110320092']
        for i, (fr, en) in enumerate(zip(left_lines, right_lines)):
            baseline = 24.75 + i * 10.125
            self.text(fr, 92.25, baseline, size=7.043, color=colors.HexColor('#222222'), align='center')
            self.text(en, 503.25, baseline, size=7.043, color=colors.HexColor('#222222'), align='center')
        logo = _image(context.get('annual_logo_path') or context.get('bulletin_logo_path'))
        if logo:
            self.pdf.drawImage(logo, 269.25, PAGE_H - 76.5, width=57, height=57.75, mask='auto')
        self.text('BULLETIN ANNUEL', PAGE_W/2, 106.5, size=17.625, align='center')
        school_class = student.school_class
        section_name = school_class.department.section.name if school_class and school_class.department and school_class.department.section else ''
        self.text('SECTION ' + str(section_name).upper().replace('SECTION ', ''), PAGE_W/2, 124.75,
                  size=9.9, color=BLUE, align='center', max_width=RIGHT-LEFT-20, char_space=.67)
        self.bar(137.5)
        self.text(student.full_name, 496.25, 145.75, size=6.6, color=BLUE, align='center', max_width=165)
        self.bar(151.5)
        dob = student.dob.strftime('%d/%m/%Y') if student.dob else '—'
        left_meta = ['Noms et Prénoms : ' + student.full_name,
                     'Date de naissance : ' + dob + ' à ' + (student.birth_place or '—'),
                     'Genre : ' + (student.sex or '—'), 'Identifiant Unique : ' + (student.matricule or '—'),
                     'Redoublant : ' + ('Oui' if student.is_repeater else 'Non')]
        teacher = school_class.homeroom_teacher if school_class else None
        right_meta = ['Année Scolaire : ' + str(context.get('school_year', '—')),
                      'Classe : ' + (school_class.name if school_class else '—'),
                      'Effectif : ' + str(data.get('class_size', 0)),
                      'Professeur Principal : ' + (teacher.user.formal_name if teacher and teacher.user else '—')]
        for i, label in enumerate(left_meta):
            self.text(label, 16.5, 166.5+i*12.75, size=7.95, max_width=287)
        for i, label in enumerate(right_meta):
            self.text(label, 313.5, 166.5+i*12.75, size=7.95, max_width=208.875)

    def photo(self, row):
        image = _image(row.get('photo_path'), portrait=True) if row.get('photo_available') else None
        if image:
            self.pdf.drawImage(image, 528.75, PAGE_H-207.5, width=49.5, height=55.5, mask='auto')
        else:
            self.text('Photo non', 553.5, 200, size=6, color=colors.HexColor('#555555'), align='center')
            self.text('disponible', 553.5, 209, size=6, color=colors.HexColor('#555555'), align='center')

    def grades(self, data):
        # 18 matières / quatre catégories dans la référence. Les autres classes
        # gardent les mêmes colonnes/polices ; seules les lignes varient avec le programme.
        categories = data.get('categories', [])
        subject_count = sum(len(cat['rows']) for cat in categories)
        row_height = 11.25
        category_height = total_height = 12.75
        available = 572.25-272.25
        if subject_count*row_height+len(categories)*(category_height+total_height) > available:
            row_height = max(8.25, (available-len(categories)*(category_height+total_height))/max(subject_count, 1))
        # Le tableau commence juste après le bloc d’identité, sans espace
        # vertical inutile après « Redoublant ».
        top = 232.5
        labels = ['Matières/Enseignant', 'Notes\nannuelles', 'Trim. 1', 'Trim. 2', 'Trim. 3', 'Coef.', 'N×C', 'Rang', 'Appréciations/Signatures']
        for i, (x0, x1) in enumerate(zip(COLUMN_EDGES, COLUMN_EDGES[1:])):
            self.box(x0, x1, top, 27, GRAY)
            if i == 1:
                # Deux lignes centrées dans la hauteur de la cellule.
                first = top + 13.5 - 4.125 + 7.043 * .34
                second = top + 13.5 + 4.125 + 7.043 * .34
                self.text('Notes', (x0+x1)/2, first, size=7.043, align='center')
                self.text('annuelles', (x0+x1)/2, second, size=7.043, align='center')
            else:
                align = 'center'
                self.text(labels[i], (x0+x1)/2, top + 13.5 + 7.043 * .34,
                          size=7.043, align=align, max_width=x1-x0-6)
        top += 27
        for category in categories:
            self.row(top, category_height, [LEFT, RIGHT], [category['name']], fill=GRAY, size=7.2)
            top += category_height
            for row in category['rows']:
                for x0, x1 in zip(COLUMN_EDGES, COLUMN_EDGES[1:]):
                    self.box(x0, x1, top, row_height)
                baseline = top+row_height/2+6.9*.34
                subject = row['course'].subject.name or '—'
                teacher = row.get('teacher')
                teacher_name = teacher.user.full_name if teacher and teacher.user else '—'
                caption = '(' + teacher_name + ')'
                size, teacher_size = 6.9, 6.45
                full_width = pdfmetrics.stringWidth(subject+' ', self.fonts['bold'], size)+pdfmetrics.stringWidth(caption,self.fonts['italic'],teacher_size)
                if full_width > COLUMN_EDGES[1]-LEFT-6:
                    size = teacher_size = 6.225
                    full_width = pdfmetrics.stringWidth(subject+' ', self.fonts['bold'], size)+pdfmetrics.stringWidth(caption,self.fonts['italic'],teacher_size)
                    ratio = min(1, (COLUMN_EDGES[1]-LEFT-6)/full_width)
                    size *= ratio; teacher_size *= ratio
                self.text(subject, 17.25, baseline, size=size)
                x = 17.25+pdfmetrics.stringWidth(subject+' ', self.fonts['bold'],size)
                self.text(caption, x, baseline, size=teacher_size, kind='italic', color=colors.HexColor('#9b9b9b'))
                annual = row.get('annual')
                values = [annual]+list(row.get('terms', [None]*3))+[row.get('coef'),row.get('points'),
                          str(row['rank'])+'e' if row.get('rank') else '—']
                for index, value in enumerate(values, 1):
                    self.text(_value(value),(COLUMN_EDGES[index]+COLUMN_EDGES[index+1])/2,baseline,
                              color=_color(value) if index in (1,2,3,4) else BLACK,align='center')
                self.text(row.get('appreciation', 'Notes en attente'), 461.19, baseline,
                          color=colors.HexColor('#5a5a5a'), max_width=RIGHT-461.19-3)
                top += row_height
            self.box(LEFT,363.75,top,total_height,GRAY)
            self.box(363.75,392.25,top,total_height,GRAY)
            self.box(392.25,RIGHT,top,total_height,GRAY)
            baseline=top+total_height/2+7.043*.34
            self.text('Total Points : '+format(category['total_points'],'.1f'),360.21,baseline,size=7.043,align='right')
            self.text(category['total_coef'],377.78,baseline,size=7.043,align='center')
            average=category.get('average')
            self.text('Moyenne/20 : '+_value(average)+' — '+str(category.get('pending_count',0))+' en attente',
                      395.34,baseline,size=7.043,color=_color(average),max_width=RIGHT-398.34)
            top += total_height
        return top

    def footer(self, data, top):
        avg = data.get('overall_avg')
        edges = [LEFT,156,298.5,496.5,RIGHT]
        self.row(top,13.5,[LEFT,298.5,RIGHT],["TRAVAIL DE L'ÉLÈVE",'PROFIL DE LA CLASSE'],fill=GRAY,
                 colors_by_column={0:BLUE,1:BLUE},size=7.35)
        top += 13.5
        labels=[('Total des points',data.get('overall_points'),'Moyenne Générale de la classe',data.get('class_avg')),
                ('Coefficient',data.get('overall_coef'),'Moyenne du premier',data.get('class_high')),
                ('Moyenne annuelle',avg,'Moyenne du dernier',data.get('class_low')),
                ('Rang',str(data['rank'])+'e/'+str(data['class_size']) if data.get('rank') else '—/'+str(data.get('class_size',0)),'','')]
        for i,items in enumerate(labels):
            if i == 3:
                self.row(top,11.625,[LEFT,156,298.5,RIGHT],[ _value(v) for v in items[:2]]+[''])
            else:
                self.row(top,11.625,edges,[ _value(v) for v in items],colors_by_column={3:_color(data.get('class_low'))} if i==2 else {})
            top += 11.625
        self.row(top,13.5,[LEFT,RIGHT],['RAPPEL DES MOYENNES TRIMESTRIELLES'],fill=GRAY,colors_by_column={0:BLUE},size=7.35)
        top += 13.5
        recap_edges=[LEFT,115.6875,202.875,305.0625,392.25,494.4375,RIGHT]
        texts=[]; text_colors={}
        for i,value in enumerate(data.get('term_averages',[None,None,None])):
            texts.extend(['Trimestre '+str(i+1),_value(value)])
            text_colors[2*i+1]=_color(value)
        self.row(top,12,recap_edges,texts,colors_by_column=text_colors)
        top += 12
        self.row(top,13.5,[LEFT,298.5,RIGHT],['APPRÉCIATION DU TRAVAIL','DISCIPLINE'],fill=GRAY,colors_by_column={0:BLUE,1:BLUE},size=7.35)
        top += 13.5
        marks=data.get('work_marks',{})
        def check(active):
            return '[X] ' if active else '[ ] '
        hours=data.get('absences_total_hours',data.get('absences_justified_hours',0)+data.get('absences_non_justified_hours',0))
        days=data.get('absences_justified_days',0)+data.get('absences_non_justified_days',0)
        exclusion=data.get('conduct_exclusion_label')
        if not exclusion:
            # Un nombre de sanctions n'est pas un nombre de jours d'exclusion.
            exclusion='—'
        work=[(check(marks.get('tableau_honneur'))+"Tableau d'Honneur",check(marks.get('travail_insuffisant'))+'Compétences non acquises',"Absences Nombre d'heures",_value(hours)),
              (check(marks.get('encouragements'))+'Encouragements',check(marks.get('bon_travail'))+'Compétences moyennement acquises','Absences Nombre de jours',str(days)),
              (check(marks.get('felicitations'))+'Félicitations',check(avg is not None and 12<=avg<14)+'Compétences bien acquises',"Exclusions Nombre d'heures",'—'),
              ('',check(avg is not None and 14<=avg<16)+'Compétences très bien acquises','Exclusions Nombre de jours',exclusion),
              ('','',check(data.get('avert_conduite'))+'Avert. Conduite',check(data.get('blame_conduite'))+'Blâme Conduite')]
        for i,texts in enumerate(work):
            self.row(top,15,edges,texts,colors_by_column={3:RED} if i==3 and exclusion!='—' else {})
            top += 15
        self.box(LEFT,389.25,top,49.5,GRAY)
        self.box(389.25,RIGHT,top,49.5,GRAY)
        self.text('DÉCISION DU CONSEIL DE CLASSE',17.25,top+9.75,color=BLUE)
        self.text('[ ] ADMIS(E) EN CLASSE DE : ______________________________',17.25,top+19.5)
        self.text('[ ] REDOUBLE LA CLASSE DE : ____________________________',17.25,top+32.25)
        self.text('[ ] Exclu(e)  [ ] Compétences non acquises  [ ] Conduite  [ ] Ne peut tripler  [ ] Démissionnaire  [ ] Insolvabilité',
                  17.25,top+45,max_width=369)
        self.text('TIBATI, le ______________',485.1,top+9.75,color=colors.HexColor('#6b7385'),align='center')
        self.text('LE PROVISEUR',485.1,top+24.75,color=BLUE,align='center')
        return top+49.5


def render_annual_bulletins_pdf(**context):
    rows=context.get('students_data')
    if rows is None:
        rows=[{'student':context['student'],'data':context['data'],
               'photo_path':context.get('student_photo_path'),'photo_available':context.get('photo_available',False)}]
    output=BytesIO()
    pdf=canvas.Canvas(output,pagesize=(PAGE_W,PAGE_H),pageCompression=1)
    pdf.setTitle('Bulletins annuels – Lycée Technique de Tibati')
    fonts=_fonts(context)
    for row in rows:
        if not row.get('data'):
            continue
        page=AnnualPage(pdf,fonts)
        page.header(row['student'],row['data'],context)
        page.photo(row)
        bottom=page.footer(row['data'],page.grades(row['data']))
        if bottom>PAGE_H-13.5:
            raise ValueError('Annual imported model does not fit on one page')
        pdf.showPage()
    pdf.save()
    output.seek(0)
    return output
