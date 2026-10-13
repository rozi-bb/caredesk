"""Calls to the backend shared by the API and Telegram tests."""

import json
from typing import Any

import psycopg
from fastapi.testclient import TestClient

Events = list[tuple[str, dict[str, Any]]]


def sign_in(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def new_thread(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/threads", headers=headers)
    assert response.status_code == 201
    return str(response.json()["thread_id"])


def parse_events(text: str) -> Events:
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def chat(client: TestClient, headers: dict[str, str], thread: str, text: str) -> Events:
    response = client.post(
        f"/threads/{thread}/messages", headers=headers, json={"content": text}
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_events(response.text)


def answer_text(events: Events) -> str:
    return "".join(data["text"] for event, data in events if event == "token")


def usage_rows(db: str, email: str, channel: str | None = None) -> int:
    with psycopg.connect(db) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM usage_events u JOIN accounts a ON a.id = u.account_id "
            "WHERE a.email = %s AND (%s::text IS NULL OR u.channel = %s)",
            (email, channel, channel),
        ).fetchone()
        assert row is not None
        return int(row[0])
