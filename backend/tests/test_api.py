"""Integration tests for REST API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from jiandou.api.app import create_app
    app = create_app()
    return TestClient(app)


class TestSystemEndpoints:
    def test_get_system_info(self, client):
        resp = client.get("/api/v1/system/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "chip" in data
        assert "ram_gb" in data
        assert "tier" in data
        assert data["tier"] in ("low", "medium", "high", "ultra")

    def test_get_system_config(self, client):
        resp = client.get("/api/v1/system/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "server" in data
        assert "engine" in data
        assert "generation" in data

    def test_patch_system_config(self, client):
        resp = client.patch("/api/v1/system/config", json={
            "generation": {"width": 640, "height": 480}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["generation"]["width"] == 640
        assert data["generation"]["height"] == 480


class TestGenerateEndpoint:
    def test_create_generation(self, client):
        resp = client.post("/api/v1/generate", json={
            "mode": "t2v",
            "prompt": "a beautiful sunset over mountains",
            "preset": "fast",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"]
        assert data["mode"] == "t2v"
        assert data["status"] == "pending"
        assert data["prompt"] == "a beautiful sunset over mountains"
        assert data["preset"] == "fast"
        assert data["width"] == 512  # Fast preset
        assert data["steps"] == 4

    def test_create_generation_with_params(self, client):
        resp = client.post("/api/v1/generate", json={
            "mode": "i2v",
            "prompt": "animate this",
            "width": 1024,
            "height": 576,
            "steps": 12,
            "cfg": 3.0,
            "seed": 42,
            "preset": "quality",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["width"] == 1024
        assert data["steps"] == 12
        assert data["seed"] == 42

    def test_create_generation_invalid_mode(self, client):
        resp = client.post("/api/v1/generate", json={
            "mode": "invalid",
            "prompt": "test",
        })
        assert resp.status_code == 422  # Validation error

    def test_create_generation_empty_prompt(self, client):
        resp = client.post("/api/v1/generate", json={
            "mode": "t2v",
            "prompt": "",
        })
        assert resp.status_code == 422


class TestTasksEndpoint:
    def test_list_tasks(self, client):
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    def test_list_tasks_with_filter(self, client):
        resp = client.get("/api/v1/tasks?status=pending")
        assert resp.status_code == 200

    def test_get_nonexistent_task(self, client):
        resp = client.get("/api/v1/tasks/nonexistent-id")
        assert resp.status_code == 404

    def test_delete_nonexistent_task(self, client):
        resp = client.delete("/api/v1/tasks/nonexistent-id")
        assert resp.status_code == 404


class TestModelsEndpoint:
    def test_list_models(self, client):
        resp = client.get("/api/v1/models")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_available_models(self, client):
        resp = client.get("/api/v1/models/available?repo=Lightricks/LTX-2")
        assert resp.status_code == 200
        data = resp.json()
        assert "repo" in data
        assert "files" in data


class TestPromptEndpoint:
    def test_enhance_prompt(self, client):
        resp = client.post("/api/v1/prompt/enhance", json={
            "prompt": "a cat walking",
            "style": "cinematic",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["original"] == "a cat walking"
        assert "a cat walking" in data["enhanced"]
        assert data["style"] == "cinematic"

    def test_enhance_prompt_default_style(self, client):
        resp = client.post("/api/v1/prompt/enhance", json={
            "prompt": "a dog running",
        })
        assert resp.status_code == 200
        assert "a dog running" in resp.json()["enhanced"]


class TestOpenAPI:
    def test_openapi_schema(self, client):
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["openapi"] == "3.1.0"
        assert len(data["paths"]) >= 8

    def test_swagger_ui(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200

    def test_redoc(self, client):
        resp = client.get("/api/redoc")
        assert resp.status_code == 200


class TestWebSocket:
    def test_websocket_queue(self, client):
        with client.websocket_connect("/ws/queue") as ws:
            ws.send_text("ping")
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_websocket_task(self, client):
        # Create a task first
        resp = client.post("/api/v1/generate", json={
            "mode": "t2v",
            "prompt": "ws test",
        })
        task_id = resp.json()["id"]

        with client.websocket_connect(f"/ws/tasks/{task_id}") as ws:
            # First message is task.status (current state)
            data = ws.receive_json()
            assert data["type"] == "task.status"
            # Then ping/pong
            ws.send_text("ping")
            data = ws.receive_json()
            assert data["type"] == "pong"


class TestErrorHandling:
    def test_404_on_unknown_api_path(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_validation_error_format(self, client):
        resp = client.post("/api/v1/generate", json={"mode": "t2v"})
        assert resp.status_code == 422
