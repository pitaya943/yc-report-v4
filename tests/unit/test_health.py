import socket

from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app


def test_health_is_200_when_the_database_answers(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_503_without_detail_when_the_database_does_not_answer(clock):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed_port = s.getsockname()[1]
    settings = load_settings(
        {"DATABASE_URL": f"postgresql://someone:hunter2@127.0.0.1:{closed_port}/yc", "APP_ENV": "test"}
    )

    with TestClient(create_app(settings, clock)) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
