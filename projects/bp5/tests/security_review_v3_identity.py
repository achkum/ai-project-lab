"""Isolated immutable account identity regression; never accesses production data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import test_production as fixture
from fastapi.testclient import TestClient

with TestClient(fixture.production.app) as client:
    def register():
        response = client.post('/api/auth/register', headers=fixture.ORIGIN,
            json={'username': 'identity-review', 'password': 'correct horse battery staple',
                  'invite': fixture.st.create_invite()})
        assert response.status_code == 200, response.text
        return response.json()
    first = register()
    first_id = first['user']['id']
    assert first_id
    assert client.get('/api/auth/session').json()['user']['id'] == first_id
    headers = {**fixture.ORIGIN, 'x-csrf-token': first['csrf']}
    assert client.post('/api/auth/logout', headers=headers, json={}).status_code == 200
    login = client.post('/api/auth/login', headers=fixture.ORIGIN,
        json={'username': 'identity-review', 'password': 'correct horse battery staple'})
    assert login.status_code == 200, login.text
    assert login.json()['user']['id'] == first_id
    headers = {**fixture.ORIGIN, 'x-csrf-token': login.json()['csrf']}
    assert client.request('DELETE', '/api/account', headers=headers,
        json={'password': 'correct horse battery staple'}).status_code == 200
    second = register()
    assert second['user']['username'] == first['user']['username']
    assert second['user']['id'] != first_id
    assert client.get('/api/auth/session').json()['user']['id'] == second['user']['id']
    print('IMMUTABLE_IDENTITY_PASS: register/session/login retain account ID; recreated username gets different ID')
