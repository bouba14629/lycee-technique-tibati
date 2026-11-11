"""Test SQLite isolé ; décodage réel des QR via zxing-cpp (outil de test).
Lancer : PYTHONPATH=flask_app python3 flask_app/bulletin_qr_pdf_feature_test.py
"""
import os
import io
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, unquote

os.environ['DATABASE_URL'] = 'sqlite:////tmp/ltt-bulletin-qr-pdf.sqlite'
os.environ['LTT_ENV'] = 'development'
os.environ.setdefault('LTT_INITIAL_ADMIN_PASSWORD', 'QrTest#2026')

import zxingcpp
from PIL import Image
from pypdf import PdfReader
from itsdangerous import URLSafeSerializer
from app import app
from models import db, AppSetting, Section, Department, SchoolClass, User, Teacher, Subject, Course, ScheduleEntry, Student, Grade
from utils import bulletin_data, annual_bulletin_data
from pdf_utils import render_pdf, get_student_photo_source
from bulletin_qr import QR_SALT


def check_pdf(raw, students, term):
    reader = PdfReader(io.BytesIO(raw))
    assert len(reader.pages) == len(students)
    urls = []
    for page, student in zip(reader.pages, students):
        decoded = []
        for item in page.images:
            result = zxingcpp.read_barcode(item.image)
            if result:
                decoded.append(result.text)
        assert len(decoded) == 1, (student.id, decoded)
        url = decoded[0]
        links = [annotation.get_object().get('/A', {}).get('/URI')
                 for annotation in page.get('/Annots', [])]
        assert url in links
        token = unquote(urlsplit(url).path.rsplit('/', 1)[-1])
        payload = URLSafeSerializer(app.config['SECRET_KEY'], salt=QR_SALT).loads(token)
        assert payload == {'s':student.id, 't':term, 'y':'2026-2027'}
        assert student.matricule in page.extract_text() and student.full_name in page.extract_text()
        urls.append(url)
    assert len(set(urls)) == len(students)
    return reader, urls


def main():
    with tempfile.TemporaryDirectory(prefix='ltt-qr-pdf-') as root, app.app_context():
        assert db.engine.url.drivername == 'sqlite' and db.engine.url.database == '/tmp/ltt-bulletin-qr-pdf.sqlite'
        db.drop_all(); db.create_all()
        db.session.add(AppSetting(current_school_year='2026-2027'))
        director = User(username='qr.director', full_name='Directeur Test', role='directeur', active=True, must_change_password=False)
        director.set_password('QrTest#2026')
        teacher_user = User(username='qr.teacher', full_name='DJIMDO ALI', civility='Mme.', role='enseignant', active=True)
        teacher_user.set_password('QrTest#2026')
        section = Section(name='Section Industrielle', code='QR')
        db.session.add_all([director,teacher_user,section]); db.session.flush()
        department = Department(name='Filière QR', code='QR', section_id=section.id)
        db.session.add(department); db.session.flush()
        cls = SchoolClass(name='TERMINALE ESF', level='TA', department_id=department.id)
        teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
        db.session.add_all([cls,teacher]); db.session.flush()
        cls.homeroom_teacher_id = teacher.id
        subject = Subject(name='Français', coefficient=2, category='Enseignements Généraux', department_id=department.id)
        db.session.add(subject); db.session.flush()
        course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=cls.id)
        db.session.add(course); db.session.flush()
        db.session.add(ScheduleEntry(course_id=course.id, day='Lundi', start_time='08:00', end_time='09:00', published=True))
        students = []
        for index, (name, color) in enumerate([('Amina',(220,20,20)), ('Bello',None), ('Chantal',(20,220,20))]):
            path = None
            if color:
                path = str(Path(root)/f'{index}.png')
                Image.new('RGB',(480,640),color).save(path)
            student = Student(first_name=name, last_name='Test', matricule=f'QR-PDF-{index+1}', class_id=cls.id, photo=path, sex='F')
            db.session.add(student); db.session.flush()
            db.session.add(Grade(student_id=student.id, course_id=course.id, term='Trimestre 1', value=[8,13,17][index], sequence=1, type='Évaluation'))
            students.append(student)
        db.session.commit()
        initial_grades = [(g.id,g.value) for g in Grade.query.order_by(Grade.id).all()]
        initial_photo_values = [s.photo for s in students]
        with app.test_request_context('/',base_url='https://lt-tibati.com'):
            for term, template, data_fn in [('Trimestre 1','pdf/class_bulletins_pdf.html',lambda s:bulletin_data(s,'Trimestre 1')),
                                            ('Annuel','pdf/class_annual_bulletins_pdf.html',annual_bulletin_data)]:
                rows=[]
                for student in students:
                    source=get_student_photo_source(student)
                    rows.append({'student':student,'data':data_fn(student),'photo_path':source,'photo_available':bool(source),'bulletin_ref':student.matricule})
                common=dict(school_year='2026-2027',term=term,term_ordinal='PREMIER',TERM_SEQ_A=1,TERM_SEQ_B=2,approval=None)
                grouped=render_pdf(template,students_data=rows,**common)
                assert grouped is not None
                raw=grouped.getvalue()
                Path('/tmp/ltt-qr-'+('annual' if term=='Annuel' else 'quarterly')+'-proof.pdf').write_bytes(raw)
                reader,urls=check_pdf(raw,students,term)
                for index,row in enumerate(rows):
                    solo_template='pdf/bulletin_annual_pdf.html' if term=='Annuel' else 'pdf/bulletin_pdf.html'
                    single=render_pdf(solo_template,student=row['student'],data=row['data'],student_photo_path=row['photo_path'],photo_available=row['photo_available'],**common)
                    _,single_urls=check_pdf(single.getvalue(),[row['student']],term)
                    assert single_urls[0] == urls[index]
                    assert PdfReader(single).pages[0].extract_text() == reader.pages[index].extract_text()
                with app.test_client() as client:
                    client.post('/login',data={'username':'qr.director','password':'QrTest#2026'})
                    scanned=client.get(urlsplit(urls[1]).path)
                    assert scanned.status_code==200 and scanned.mimetype=='application/pdf'
                    assert students[1].matricule in PdfReader(io.BytesIO(scanned.data)).pages[0].extract_text()
                print('QR_PDF_DECODE_STUDENT_TERM_AND_INDIVIDUAL_GROUPED_PARITY_OK',term,flush=True)
        assert initial_grades == [(g.id,g.value) for g in Grade.query.order_by(Grade.id).all()]
        assert initial_photo_values == [s.photo for s in students]
    print('BULLETIN_QR_PDF_FEATURE_TEST_OK')


if __name__=='__main__':
    main()
