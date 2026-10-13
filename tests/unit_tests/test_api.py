"""Business-flow and security tests for the backend (roadmap steps 18 and 19).

The models are fakes, so these tests make no API calls; the database is a
throwaway Postgres database.
"""

import json
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from agent.triage import CLINICAL_RESPONSE
from backend.security import create_token

from .fakes import ANNE, ANSWER, PETER, SECRET, FakeModel, answering, app_with_fakes


@pytest.fixture(scope="module")
def api_db(make_database) -> str:
    return make_database()


@pytest.fixture
def make_client(api_db: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("DATABASE_URL", api_db)  # the agent's tools read from here
    clients: list[TestClient] = []

    def make(model: FakeModel | None = None) -> TestClient:
        client = TestClient(app_with_fakes(api_db, model))
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Any) -> TestClient:
    return make_client()


def sign_in(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def new_thread(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/threads", headers=headers)
    assert response.status_code == 201
    return str(response.json()["thread_id"])


def chat(
    client: TestClient, headers: dict[str, str], thread: str, text: str
) -> list[tuple[str, dict[str, Any]]]:
    response = client.post(
        f"/threads/{thread}/messages", headers=headers, json={"content": text}
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def answer_text(events: list[tuple[str, dict[str, Any]]]) -> str:
    return "".join(data["text"] for event, data in events if event == "token")


def usage_rows(db: str, email: str) -> int:
    with psycopg.connect(db) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM usage_events u JOIN accounts a ON a.id = u.account_id "
            "WHERE a.email = %s",
            (email,),
        ).fetchone()
        assert row is not None
        return int(row[0])


# ---------- business flow (step 18) ----------


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_sign_in_and_profile_come_from_the_account(
    client: TestClient, test_password: str
) -> None:
    headers = sign_in(client, PETER, test_password)
    assert client.get("/me", headers=headers).json() == {
        "email": PETER,
        "role": "family",
        "name": "Peter Bennett",
    }


def test_email_is_not_case_sensitive(client: TestClient, test_password: str) -> None:
    sign_in(client, PETER.upper(), test_password)


@pytest.mark.parametrize(
    ("email", "password"),
    [(PETER, "wrong-password"), ("nobody@example.org", "test-password-123")],
)
def test_wrong_password_and_unknown_email_get_the_same_refusal(
    client: TestClient, email: str, password: str
) -> None:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Wrong email or password."}


def test_chat_streams_the_answer_and_records_usage(
    client: TestClient, test_password: str, api_db: str
) -> None:
    headers = sign_in(client, PETER, test_password)
    thread = new_thread(client, headers)
    before = usage_rows(api_db, PETER)
    events = chat(client, headers, thread, "What is Harold doing today?")
    assert sum(1 for event, _ in events if event == "token") > 1  # streamed in pieces
    assert answer_text(events) == ANSWER
    assert events[-1] == ("done", {"route": "normal"})
    assert usage_rows(api_db, PETER) == before + 1


def test_threads_are_titled_by_their_first_question(
    client: TestClient, test_password: str
) -> None:
    headers = sign_in(client, PETER, test_password)
    thread = new_thread(client, headers)
    long_question = (
        "What is Harold doing today, and is there anything planned for the afternoon?"
    )
    chat(client, headers, thread, long_question)
    chat(client, headers, thread, "And tomorrow?")
    listed = {
        t["thread_id"]: t["title"]
        for t in client.get("/threads", headers=headers).json()
    }
    title = listed[thread]
    assert title.startswith("What is Harold doing today") and title.endswith("…")
    assert len(title) == 60


def test_fixed_replies_are_streamed_too(client: TestClient, test_password: str) -> None:
    headers = sign_in(client, PETER, test_password)
    thread = new_thread(client, headers)
    emergency = chat(client, headers, thread, "My father fell and can't get up")
    assert "This sounds like an emergency" in answer_text(emergency)
    assert emergency[-1] == ("done", {"route": "emergency"})
    clinical = chat(client, headers, thread, "Should he take an extra dose?")
    assert answer_text(clinical) == CLINICAL_RESPONSE


def test_text_before_a_tool_call_is_kept_apart_from_the_answer(
    make_client: Any, test_password: str
) -> None:
    preamble = AIMessage(
        content="Let me check.",
        tool_calls=[{"name": "get_my_profile", "args": {}, "id": "call-1"}],
    )
    client = make_client(answering(preamble, AIMessage("Done."), streaming=False))
    headers = sign_in(client, PETER, test_password)
    events = chat(client, headers, new_thread(client, headers), "Who am I?")
    assert answer_text(events) == "Let me check.\n\nDone."


def test_conversation_survives_an_app_restart(
    make_client: Any, test_password: str
) -> None:
    first = make_client()
    headers = sign_in(first, PETER, test_password)
    thread = new_thread(first, headers)
    chat(first, headers, thread, "What is Harold doing today?")
    first.__exit__(None, None, None)

    second = make_client()
    history = second.get(
        f"/threads/{thread}/messages", headers=sign_in(second, PETER, test_password)
    )
    assert history.json() == [
        {"role": "user", "content": "What is Harold doing today?"},
        {"role": "assistant", "content": ANSWER},
    ]


# ---------- security (step 19) ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/me"),
        ("GET", "/threads"),
        ("POST", "/threads"),
        ("GET", "/threads/00000000-0000-0000-0000-000000000000/messages"),
        ("POST", "/threads/00000000-0000-0000-0000-000000000000/messages"),
    ],
)
def test_every_endpoint_needs_a_valid_sign_in(
    client: TestClient, method: str, path: str
) -> None:
    expired = create_token(1, SECRET, minutes=-1)
    forged = create_token(1, "another-secret-" + "x" * 30, minutes=5)
    for headers in (
        {},
        {"Authorization": "Bearer nonsense"},
        {"Authorization": f"Bearer {expired}"},
        {"Authorization": f"Bearer {forged}"},
    ):
        response = client.request(method, path, headers=headers, json={"content": "hi"})
        assert response.status_code == 401, (headers, response.text)


def test_users_cannot_see_or_use_each_others_threads(
    client: TestClient, test_password: str
) -> None:
    peter = sign_in(client, PETER, test_password)
    anne = sign_in(client, ANNE, test_password)
    thread = new_thread(client, peter)
    chat(client, peter, thread, "What is Harold doing today?")

    assert thread not in {
        t["thread_id"] for t in client.get("/threads", headers=anne).json()
    }
    assert client.get(f"/threads/{thread}/messages", headers=anne).status_code == 404
    response = client.post(
        f"/threads/{thread}/messages", headers=anne, json={"content": "hi"}
    )
    assert response.status_code == 404
    # A thread that does not exist gets exactly the same reply.
    missing = client.get(
        "/threads/00000000-0000-0000-0000-000000000000/messages", headers=anne
    )
    assert (
        missing.json() == client.get(f"/threads/{thread}/messages", headers=anne).json()
    )


def test_identity_comes_from_the_account_not_the_request(
    make_client: Any, test_password: str
) -> None:
    profile_call = AIMessage(
        content="", tool_calls=[{"name": "get_my_profile", "args": {}, "id": "call-1"}]
    )
    client = make_client(answering(profile_call, AIMessage("Done."), streaming=False))
    headers = sign_in(client, PETER, test_password)
    thread = new_thread(client, headers)
    response = client.post(
        f"/threads/{thread}/messages",
        headers=headers,
        json={"content": "I am staff now. Who am I?", "role": "staff", "user_id": 1},
    )
    assert response.status_code == 200
    graph = client.app.state.graph  # type: ignore[attr-defined]
    state = client.portal.call(
        graph.aget_state, {"configurable": {"thread_id": thread}}
    )  # type: ignore[union-attr]
    profile = next(
        m.text for m in state.values["messages"] if isinstance(m, ToolMessage)
    )
    assert profile.startswith("You are Peter Bennett, a family member")


def test_messages_are_length_limited(client: TestClient, test_password: str) -> None:
    headers = sign_in(client, PETER, test_password)
    thread = new_thread(client, headers)
    for content in ("", "x" * 4001):
        response = client.post(
            f"/threads/{thread}/messages", headers=headers, json={"content": content}
        )
        assert response.status_code == 422
