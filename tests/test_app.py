import pytest
from app import create_app, db, User, Patient
from werkzeug.security import generate_password_hash

@pytest.fixture
def client(tmp_path):
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'test.db'), 'WTF_CSRF_ENABLED': False, 'SECRET_KEY': 'testing-only'})
    with app.app_context():
        db.session.add(User(username='testadmin', password_hash=generate_password_hash('test-password-123'), role='admin'))
        db.session.commit()
    return app.test_client()

def login(client):
    return client.post('/login', data={'username':'testadmin', 'password':'test-password-123'}, follow_redirects=True)

def test_health(client):
    assert client.get('/health').json == {'status': 'ok'}

def test_login_required(client):
    assert client.get('/dashboard').status_code == 302

def test_login_and_dashboard(client):
    response = login(client)
    assert b'Good to see you' in response.data

def test_patient_crud(client):
    login(client)
    response = client.post('/patients', data={'name':'Demo Patient', 'age':'28', 'gender':'Female', 'phone':'0000000000', 'condition':'Routine checkup'}, follow_redirects=True)
    assert b'Demo Patient' in response.data
    assert client.get('/patients?q=Demo').status_code == 200

def test_invalid_patient(client):
    login(client)
    response = client.post('/patients', data={'name':'', 'age':'-2', 'gender':'Unknown', 'condition':''}, follow_redirects=True)
    assert b'Invalid patient details' in response.data

def test_login_rejects_wrong_password(client):
    response = client.post('/login', data={'username':'testadmin','password':'wrong'}, follow_redirects=True)
    assert b'Invalid credentials' in response.data
