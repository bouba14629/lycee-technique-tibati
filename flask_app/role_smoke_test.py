import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app


ACCOUNTS = [
    ('directeur', 'proviseur1', 'Direction@2026'),
    ('censeur_stt', 'censeur.stt', 'CenseurSTT@2026'),
    ('censeur_ind', 'censeur.ind', 'CenseurIND@2026'),
    ('censeur_eg', 'censeur.eg', 'CenseurEG@2026'),
    ('censeur_crm', 'censeur.crm', 'CenseurCRM@2026'),
    ('surveillant', 'surveillant.stt', 'SurveilSTT@2026'),
    ('chef_travaux', 'cheftravaux.stt', 'TravauxSTT@2026'),
    ('chef_crm', 'chefcrm1', 'CentreCRM@2026'),
    ('orientation', 'orientation1', 'Orient@2026'),
    ('enseignant', 'demo.aca', 'Demo@2026'),
    ('eleve', 'demo.eleve', 'Demo@2026'),
    ('parent', 'demo.parent', 'Demo@2026'),
]


def main():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        for label, username, password in ACCOUNTS:
            client.get('/logout')
            login = client.post('/login', data={'username': username, 'password': password})
            assert login.status_code in (302, 303), (label, login.status_code)
            dashboard = client.get('/dashboard')
            assert dashboard.status_code == 200, (label, dashboard.status_code)
            assert b'Erreur interne' not in dashboard.data, label
        print(f'ROLE_SMOKE_TEST_OK {len(ACCOUNTS)}')


if __name__ == '__main__':
    main()
