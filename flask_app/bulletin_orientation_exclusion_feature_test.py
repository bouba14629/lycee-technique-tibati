from pathlib import Path

utils = (Path(__file__).parent / 'utils.py').read_text(encoding='utf-8')
assert 'orientation scolaire' in utils.casefold()
# The schedule source remains independent: this change only filters bulletin data.
assert 'def build_official_grid' in utils
assert 'def bulletin_data' in utils
assert 'def annual_bulletin_data' in utils
bulletin = (Path(__file__).parent / 'templates/bulletin.html').read_text(encoding='utf-8')
pdf = (Path(__file__).parent / 'templates/pdf/_bulletin_body.html').read_text(encoding='utf-8')
assert 'row.course.subject.name' in bulletin
assert 'row.course.subject.name' in pdf
print('BULLETIN_ORIENTATION_EXCLUSION_FEATURE_TEST_OK')
