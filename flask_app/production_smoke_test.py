import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app


def main():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        health = client.get('/health')
        assert health.status_code == 200, health.status_code
        assert health.get_json()['status'] == 'ok'
        assert health.headers['X-Content-Type-Options'] == 'nosniff'
        assert health.headers['X-Frame-Options'] == 'SAMEORIGIN'
        login = client.post('/login', data={'username': 'proviseur1', 'password': 'Direction@2026'})
        assert login.status_code in (302, 303), login.status_code
        dashboard = client.get('/dashboard')
        assert dashboard.status_code == 200, dashboard.status_code
    print('PRODUCTION_SMOKE_TEST_OK')


if __name__ == '__main__':
    main()
