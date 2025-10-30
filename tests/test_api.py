import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine
from app.models import URL
from app import cache
from unittest.mock import patch

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    cache.redis_client.flushall()
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_rabbitmq():
    with patch("app.rabbit.publish_event") as mock:
        yield mock


def test_full_flow(mock_rabbitmq):
    # 1. Регистрация
    r = client.post("/register", json={"email": "t@example.com", "password": "123456"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    # 2. Создание
    r = client.post("/shorten", json={"original_url": "https://google.com"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    short_code = r.json()["short_code"]

    # 3. Список
    r = client.get("/urls", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()["urls"]) == 1

    # 4. Редирект
    r = client.get(f"/{short_code}")
    assert r.status_code == 200
    assert r.json()["original_url"] == "https://google.com"

    # 5. Кэш
    cache.redis_client.delete(short_code)
    r = client.get(f"/{short_code}")
    assert r.status_code == 200
    assert cache.get_cached_url(short_code) is not None

    # 6. RabbitMQ
    mock_rabbitmq.assert_called_once()


def test_invalid_url(mock_rabbitmq):
    client.post("/register", json={"email": "bad@example.com", "password": "123456"})
    r = client.post("/login", data={"username": "bad@example.com", "password": "123456"})
    token = r.json()["access_token"]

    r = client.post("/shorten", json={"original_url": "not-a-url"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_unauthorized_shorten():
    r = client.post("/shorten", json={"original_url": "https://x.com"})
    assert r.status_code == 401