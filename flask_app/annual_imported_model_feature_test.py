"""Régression du modèle annuel importé, base SQLite et photos synthétiques seulement."""
import io
import os
import tempfile
from datetime import date
from pathlib import Path
from PIL import Image
from pypdf import PdfReader


def main():
    with tempfile.TemporaryDirectory(prefix='ltt-annual-model-') as temp:
        os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(temp) / 'test.sqlite')
        os.environ['LTT_ENV'] = 'development'
        os.environ['LTT_BOOTSTRAP_MODE'] = 'demo'
        from app import app
        from models import (db, User, Teacher, Section, Department, SchoolClass, Subject,
                            Course, ScheduleEntry, Student, Grade, SUBJECT_CATEGORIES)
        from pdf_utils import get_student_photo_source, render_pdf
        from utils import annual_bulletin_data

        photo = Path(temp) / 'portrait.png'
        Image.new('RGB', (653, 731), (35, 90, 180)).save(photo)
        with app.test_request_context('/'):
            assert db.engine.url.drivername == 'sqlite'
            assert db.engine.url.database == str(Path(temp) / 'test.sqlite')
            db.drop_all()
            db.create_all()
            section = Section(name='Industrielle', code='TEST-ANNUEL')
            department = Department(name='Maçonnerie', code='TEST-MACO', section=section)
            school_class = SchoolClass(name='3A MACO', code='TEST-MACO-3', level='3A', department=department)
            user = User(username='test.annual.model.teacher', full_name='PAGOUI ELISEE', role='enseignant')
            user.set_password('Temporary-Test-Only#2026')
            teacher = Teacher(user=user, department=department)
            student = Student(matricule='LTT20262222', first_name='BOUBA BELL BELLO SERGE', last_name='',
                              sex='M', dob=date(2011, 8, 20), birth_place='KAELE', school_class=school_class,
                              photo=str(photo))
            db.session.add_all([section, department, school_class, user, teacher, student]); db.session.flush()
            names = [
                ['Anglais', 'ECM', 'Français', 'Informatique', 'Mathématiques', 'Sciences Physiques'],
                ['Dessin', 'Devis et Estimation', 'Santé et Sécurité', 'Technologie/Connaissance des Matériaux'],
                ['Exécution de Ferraillage', 'Exécution de Maçonnerie et Échafaudage', 'Exécution de coffrage',
                 'Mise en Œuvre du Béton', 'Ouvrages en Terre', 'PDR'],
                ['EPS', 'Travail Manuel'],
            ]
            for category, subjects in zip(SUBJECT_CATEGORIES, names):
                for name in subjects:
                    subject = Subject(name=name, coefficient=2, category=category, school_class=school_class,
                                      department=department)
                    course = Course(subject=subject, teacher=teacher, school_class=school_class)
                    db.session.add_all([subject, course]); db.session.flush()
                    db.session.add(ScheduleEntry(course=course, day='Lundi', start_time='08:00', end_time='09:00', published=True))
                    if name in ('Anglais', 'ECM'):
                        db.session.add(Grade(student=student, course=course, term='Trimestre 1', value=11.5 if name == 'Anglais' else 6.5))
            db.session.commit()
            data = annual_bulletin_data(student)
            assert data['overall_avg'] == 9 and data['overall_points'] == 36 and data['overall_coef'] == 4
            source = get_student_photo_source(student)
            credentials_before = (user.username, user.password_hash, user.plain_password)
            grade_values_before = [(grade.id, grade.value, grade.max_value, grade.term) for grade in Grade.query.order_by(Grade.id).all()]
            common = dict(school_year='2025-2026', avatar_path=None, approval=None)
            individual = render_pdf('pdf/bulletin_annual_pdf.html', student=student, data=data,
                                    student_photo_path=source, photo_available=bool(source), **common)
            grouped = render_pdf('pdf/class_annual_bulletins_pdf.html',
                                 students_data=[dict(student=student, data=data, photo_path=source, photo_available=bool(source))],
                                 **common)
            assert individual and grouped
            samples = []
            for label, buffer in [('individual', individual), ('grouped', grouped)]:
                raw = buffer.getvalue()
                target = Path('/tmp/ltt-new-annual-' + label + '.pdf')
                target.write_bytes(raw)
                reader = PdfReader(io.BytesIO(raw))
                assert len(reader.pages) == 1, (label, len(reader.pages))
                page = reader.pages[0]
                text = ' '.join(page.extract_text().split())
                for expected in ['BULLETIN ANNUEL', 'LTT20262222', '3A MACO', 'RAPPEL DES MOYENNES TRIMESTRIELLES',
                                 'APPRÉCIATION DU TRAVAIL', 'DÉCISION DU CONSEIL DE CLASSE',
                                 'TIBATI, le ______________', 'LE PROVISEUR', 'Trim. 1', 'Trim. 2', 'Trim. 3']:
                    assert expected in text, (label, expected, text)
                assert "VISA DU CHEF D'ÉTABLISSEMENT" not in text
                assert all(name in text for subjects in names for name in subjects)
                assert abs(float(page.mediabox.width) - 595.92) < .01
                assert abs(float(page.mediabox.height) - 842.88) < .01
                assert len([im for im in page.images if im.image.width < 320]) == 1
                rectangles = [tuple(round(float(value), 3) for value in operands)
                              for operands, operation in page.get_contents().operations if operation == b're']
                for x0, x1 in zip([13.5,212.25,258,293.25,328.5,363.75,392.25,427.5,457.5],
                                  [212.25,258,293.25,328.5,363.75,392.25,427.5,457.5,582]):
                    assert (x0, round(842.88-245.25-27,3), round(x1-x0,3),27) in rectangles
                assert (13.5, round(842.88-145.5-2.25,3),568.5,2.25) in rectangles
                assert (13.5, round(842.88-163.5-2.25,3),568.5,2.25) in rectangles
                fonts = [font.get_object() for font in page['/Resources']['/Font'].values()]
                liberation = [font for font in fonts if 'LiberationSans' in str(font.get('/BaseFont',''))]
                assert len(liberation) >= 2
                assert all('/FontFile2' in font['/FontDescriptor'].get_object() for font in liberation)
                samples.append(text)
                print('ANNUAL_IMPORTED_MODEL_PDF_OK', label, target, flush=True)
            assert samples[0] == samples[1], 'Les modèles annuels individuels et groupés divergent'
            print('ANNUAL_IMPORTED_INDIVIDUAL_GROUPED_PARITY_OK', flush=True)
            assert credentials_before == (user.username, user.password_hash, user.plain_password)
            assert grade_values_before == [(grade.id, grade.value, grade.max_value, grade.term) for grade in Grade.query.order_by(Grade.id).all()]

    print('ANNUAL_IMPORTED_MODEL_FEATURE_TEST_OK', flush=True)


if __name__ == '__main__':
    main()
