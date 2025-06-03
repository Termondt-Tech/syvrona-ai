def test_app_exists(app):
    assert app is not None


def test_app_is_testing(app):
    assert app.config["TESTING"]


def test_database_initialization(client):
    response = client.get("/")
    assert response.status_code == 200


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_readyz(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json == {"status": "ready"}
