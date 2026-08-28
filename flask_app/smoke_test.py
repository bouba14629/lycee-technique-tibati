import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import User


def main():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as client:
        response = client.get('/login')
        assert response.status_code == 200, response.status_code
        response = client.post('/login', data={'username': 'proviseur1', 'password': 'Direction@2026'}, follow_redirects=False)
        assert response.status_code in (302, 303), response.status_code
        response = client.get('/dashboard')
        assert response.status_code == 200, response.status_code
        with app.app_context():
            assert User.query.count() > 0
    print('SMOKE_TEST_OK')


if __name__ == '__main__':
    main()
