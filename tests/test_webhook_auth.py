import os

os.environ.setdefault("GITLAB_TOKEN", "test-token")
os.environ.setdefault("GITLAB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_webhook_rejects_missing_token():
    response = client.post("/webhook/gitlab", json={})
    assert response.status_code == 401


def test_webhook_rejects_wrong_token():
    response = client.post(
        "/webhook/gitlab", json={}, headers={"X-Gitlab-Token": "wrong"}
    )
    assert response.status_code == 401


def test_webhook_accepts_correct_token():
    response = client.post(
        "/webhook/gitlab",
        json={"object_kind": "note"},
        headers={"X-Gitlab-Token": "test-secret"},
    )
    assert response.status_code == 200
