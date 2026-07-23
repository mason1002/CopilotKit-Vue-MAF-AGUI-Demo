import json

from fastapi.testclient import TestClient

from main import app, create_demo_token


client = TestClient(app)
origin = "http://127.0.0.1:5174"


def direct_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {token}",
        "Origin": origin,
        "X-Demo-Request-ID": "api-test-request",
        "X-Demo-Transport": "direct",
    }


def agui_payload(message: str = "direct api test") -> dict[str, object]:
    return {
        "threadId": "api-test-thread",
        "runId": "api-test-run",
        "tools": [],
        "context": [],
        "forwardedProps": {},
        "state": {},
        "messages": [{"id": "message-1", "role": "user", "content": message}],
    }


def parse_events(body: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data:").strip())
        for line in body.splitlines()
        if line.startswith("data:")
    ]


def test_direct_cors_preflight_allows_required_headers() -> None:
    response = client.options(
        "/agent",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization,content-type,x-demo-request-id,x-demo-transport"
            ),
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "x-demo-request-id" in allowed
    assert "x-demo-transport" in allowed


def test_direct_agent_rejects_missing_bearer_token() -> None:
    response = client.post("/agent", json=agui_payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing bearer token"}


def test_direct_agent_rejects_invalid_bearer_token() -> None:
    response = client.post(
        "/agent",
        json=agui_payload(),
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid bearer token"}


def test_direct_app_exposes_agent_without_runtime_routes() -> None:
    paths = app.openapi()["paths"]

    assert "/agent" in paths
    assert "/copilotkit" not in paths
    assert "/copilotkit/info" not in paths


def test_direct_local_agent_returns_complete_agui_stream() -> None:
    response = client.post(
        "/agent",
        json=agui_payload("confirm direct transport"),
        headers=direct_headers(create_demo_token()),
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_events(response.text)
    event_types = [event["type"] for event in events]
    assert event_types[0] == "RUN_STARTED"
    assert "TEXT_MESSAGE_START" in event_types
    assert "TEXT_MESSAGE_CONTENT" in event_types
    assert "TEXT_MESSAGE_END" in event_types
    assert "MESSAGES_SNAPSHOT" in event_types
    assert event_types[-1] == "RUN_FINISHED"

    text = "".join(
        str(event.get("delta", ""))
        for event in events
        if event["type"] == "TEXT_MESSAGE_CONTENT"
    )
    assert "directly from Vue" in text
    assert "confirm direct transport" in text