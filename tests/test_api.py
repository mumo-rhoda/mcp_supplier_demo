import pytest
from fastapi.testclient import TestClient
from app.api import app
@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'test.db'))
    with TestClient(app) as c: yield c
D={'name':'Example Ltd','country':'Kenya','tax_id':'ABC123'}
def test_api(client):
    assert len(client.get('/suppliers').json()['suppliers'])==3
    assert len(client.get('/suppliers',params={'country':'Uganda','status':'active'}).json()['suppliers'])==1
    assert client.get('/suppliers/KE001').json()['supplier']['id']=='KE001'
    assert client.post('/suppliers/validate',json=D).json()['valid']
    r=client.post('/suppliers',json=D); assert r.json()['ok']
    sid=r.json()['supplier']['id']
    assert client.post('/suppliers',json=D).json()['supplier']['id']==sid
    assert not client.post('/suppliers/validate',json={**D,'name':'Other'}).json()['valid']
    assert not client.post('/suppliers',json={**D,'country':'Germany'}).json()['ok']
    assert client.get('/suppliers',params={'country':'Germany'}).status_code==400
    assert client.post('/suppliers',json={'name':12}).status_code==422
    assert client.get('/health',headers={'x-trace-id':'example-trace'}).headers['x-trace-id']=='example-trace'

def test_database_failure(client,monkeypatch):
    from app import store
    def fail(): raise RuntimeError('secret connection string')
    monkeypatch.setattr(store,'connect',fail)
    r=client.get('/suppliers'); assert r.status_code==503 and 'secret' not in r.text
