import os

os.environ.setdefault("GITLAB_TOKEN", "test-token")
os.environ.setdefault("GITLAB_URL", "https://gitlab.example.com")
os.environ.setdefault("GITLAB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_webhook_rejects_missing_secret():
    response = client.post("/webhook/gitlab", json={})
    assert response.status_code == 401


def test_webhook_rejects_wrong_secret():
    response = client.post(
        "/webhook/gitlab",
        headers={"X-Gitlab-Token": "wrong-secret"},
        json={},
    )
    assert response.status_code == 401


def test_webhook_accepts_correct_secret():
    response = client.post(
        "/webhook/gitlab",
        headers={"X-Gitlab-Token": "test-secret"},
        json={"object_kind": "note"},
    )
    assert response.status_code == 200
