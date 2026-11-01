"""Isolated review proof. Uses test fixture temp DB; never production data."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import test_production as fixture
from fastapi.testclient import TestClient

with fixture.st.connect() as c:
    c.execute('DELETE FROM attempts')
with TestClient(fixture.production.app) as client:
    responses = []
    for index in range(45):
        r = client.post('/api/auth/login', headers=fixture.ORIGIN,
                        json={'username': f'unknown{index}', 'password': 'wrong'})
        responses.append(r.status_code)
    with fixture.st.connect() as c:
        before = c.execute('SELECT count(*) FROM attempts').fetchone()[0]
    for index in range(45, 55):
        r = client.post('/api/auth/login', headers=fixture.ORIGIN,
                        json={'username': f'unknown{index}', 'password': 'wrong'})
        responses.append(r.status_code)
    with fixture.st.connect() as c:
        after = c.execute('SELECT count(*) FROM attempts').fetchone()[0]
    print(json.dumps({'first_40': responses[:40], 'subsequent': responses[40:],
                      'attempts_before_10_denied': before,
                      'attempts_after_10_denied': after,
                      'denied_request_growth': after-before}))
