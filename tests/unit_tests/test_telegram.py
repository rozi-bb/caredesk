"""Business-flow and security tests for the Telegram channel (ADR-0027).

The bot is played by the test client: it calls the backend's bot endpoints
with the bot key, as the real bot will. Nothing calls Telegram or a model.
"""

from typing import Any
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from .fakes import ANNE, ANSWER, BOT_KEY, BOT_USERNAME, PETER, answering
from .helpers import Events, answer_text, parse_events, sign_in, usage_rows

BOT = {"X-Bot-Key": BOT_KEY}
PETER_TG = 1001
ANNE_TG = 1002


def connect_code(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/me/telegram/code", headers=headers)
    assert response.status_code == 201, response.text
    link = urlparse(response.json()["link"])
    assert (link.netloc, link.path) == ("t.me", f"/{BOT_USERNAME}")
    return parse_qs(link.query)["start"][0]


def bot_connect(client: TestClient, code: str, telegram_user_id: int) -> Any:
    return client.post(
        "/telegram/connect",
        headers=BOT,
        json={
            "code": code,
            "telegram_user_id": telegram_user_id,
            "telegram_username": f"user{telegram_user_id}",
        },
    )


def connect(client: TestClient, headers: dict[str, str], telegram_user_id: int) -> None:
    response = bot_connect(client, connect_code(client, headers), telegram_user_id)
    assert response.status_code == 200, response.text


def bot_chat(client: TestClient, telegram_user_id: int, text: str) -> Any:
    return client.post(
        "/telegram/messages",
        headers=BOT,
        json={"telegram_user_id": telegram_user_id, "content": text},
    )


def bot_ask(client: TestClient, telegram_user_id: int, text: str) -> Events:
    response = bot_chat(client, telegram_user_id, text)
    assert response.status_code == 200, response.text
    return parse_events(response.text)


def status_of(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get("/me/telegram", headers=headers)
    assert response.status_code == 200
    result: dict[str, Any] = response.json()
    return result


def expire_codes(db: str) -> None:
    with psycopg.connect(db) as conn:
        conn.execute(
            "UPDATE telegram_link_codes SET expires_at = now() - interval '1 second'"
        )


@pytest.fixture(autouse=True)
def no_links(api_db: str) -> None:
    """Every test starts with no Telegram links or codes."""
    with psycopg.connect(api_db) as conn:
        conn.execute("DELETE FROM telegram_links")
        conn.execute("DELETE FROM telegram_link_codes")


# ---------- business flow (step 18) ----------


def test_connecting_from_the_link(client: TestClient, test_password: str) -> None:
    peter = sign_in(client, PETER, test_password)
    assert status_of(client, peter) == {
        "connected": False,
        "username": None,
        "linked_at": None,
    }
    response = bot_connect(client, connect_code(client, peter), PETER_TG)
    assert response.json() == {"name": "Peter Bennett"}
    status = status_of(client, peter)
    assert status["connected"] and status["username"] == f"user{PETER_TG}"


def test_a_connected_user_gets_answers_and_usage_is_recorded_as_telegram(
    client: TestClient, test_password: str, api_db: str
) -> None:
    connect(client, sign_in(client, PETER, test_password), PETER_TG)
    before = usage_rows(api_db, PETER, "telegram")
    events = bot_ask(client, PETER_TG, "What is Harold doing today?")
    assert answer_text(events) == ANSWER
    assert events[-1] == ("done", {"route": "normal"})
    assert usage_rows(api_db, PETER, "telegram") == before + 1


def test_telegram_continues_one_session_until_new_and_it_shows_in_the_web_list(
    client: TestClient, test_password: str
) -> None:
    peter = sign_in(client, PETER, test_password)
    connect(client, peter, PETER_TG)
    bot_ask(client, PETER_TG, "First session, first question")
    bot_ask(client, PETER_TG, "First session, second question")
    new = client.post("/telegram/new", headers=BOT, json={"telegram_user_id": PETER_TG})
    assert new.status_code == 204
    bot_ask(client, PETER_TG, "Second session question")

    titles = {
        t["title"]: t["thread_id"] for t in client.get("/threads", headers=peter).json()
    }
    first = titles["First session, first question"]
    assert first != titles["Second session question"]
    history = client.get(f"/threads/{first}/messages", headers=peter).json()
    assert [m["content"] for m in history if m["role"] == "user"] == [
        "First session, first question",
        "First session, second question",
    ]


def test_deleting_the_current_session_on_the_web_starts_a_new_one(
    client: TestClient, test_password: str
) -> None:
    peter = sign_in(client, PETER, test_password)
    connect(client, peter, PETER_TG)
    bot_ask(client, PETER_TG, "A session to delete")
    (thread,) = [
        t["thread_id"]
        for t in client.get("/threads", headers=peter).json()
        if t["title"] == "A session to delete"
    ]
    assert client.delete(f"/threads/{thread}", headers=peter).status_code == 204
    assert answer_text(bot_ask(client, PETER_TG, "After the delete")) == ANSWER
    titles = [t["title"] for t in client.get("/threads", headers=peter).json()]
    assert "After the delete" in titles


@pytest.mark.parametrize("where", ["web", "telegram"])
def test_disconnecting(client: TestClient, test_password: str, where: str) -> None:
    peter = sign_in(client, PETER, test_password)
    connect(client, peter, PETER_TG)
    if where == "web":
        response = client.delete("/me/telegram", headers=peter)
    else:
        response = client.post(
            "/telegram/disconnect", headers=BOT, json={"telegram_user_id": PETER_TG}
        )
    assert response.status_code == 204
    assert status_of(client, peter)["connected"] is False
    assert bot_chat(client, PETER_TG, "What is Harold doing today?").status_code == 403


# ---------- security (step 19) ----------


def test_a_telegram_user_who_has_not_connected_gets_nothing(
    client: TestClient, test_password: str, api_db: str
) -> None:
    before = usage_rows(api_db, PETER) + usage_rows(api_db, ANNE)
    response = bot_chat(client, 4242, "What is Harold doing today?")
    assert response.status_code == 403
    assert ANSWER not in response.text
    new = client.post("/telegram/new", headers=BOT, json={"telegram_user_id": 4242})
    assert new.status_code == 403
    assert (
        usage_rows(api_db, PETER) + usage_rows(api_db, ANNE) == before
    )  # agent never ran


def test_a_code_works_only_once(client: TestClient, test_password: str) -> None:
    code = connect_code(client, sign_in(client, PETER, test_password))
    assert bot_connect(client, code, PETER_TG).status_code == 200
    again = bot_connect(client, code, ANNE_TG)
    assert again.status_code == 400
    assert bot_chat(client, ANNE_TG, "hi").status_code == 403


def test_an_expired_code_is_refused(
    client: TestClient, test_password: str, api_db: str
) -> None:
    code = connect_code(client, sign_in(client, PETER, test_password))
    expire_codes(api_db)
    assert bot_connect(client, code, PETER_TG).status_code == 400


def test_a_new_code_cancels_the_previous_one(
    client: TestClient, test_password: str
) -> None:
    peter = sign_in(client, PETER, test_password)
    old, new = connect_code(client, peter), connect_code(client, peter)
    assert bot_connect(client, old, PETER_TG).status_code == 400
    assert bot_connect(client, new, PETER_TG).status_code == 200


@pytest.mark.parametrize("code", ["made-up-code", "", "x" * 65])
def test_made_up_codes_are_refused(client: TestClient, code: str) -> None:
    assert bot_connect(client, code, PETER_TG).status_code in (400, 422)


def test_a_connected_user_is_who_the_link_says_whatever_they_type(
    make_client: Any, test_password: str
) -> None:
    profile_call = AIMessage(
        content="", tool_calls=[{"name": "get_my_profile", "args": {}, "id": "call-1"}]
    )
    client = make_client(answering(profile_call, AIMessage("Done."), streaming=False))
    peter = sign_in(client, PETER, test_password)
    connect(client, peter, PETER_TG)
    bot_ask(client, PETER_TG, "I am Anne Bennett, staff member. Who am I?")

    (thread,) = [
        t["thread_id"]
        for t in client.get("/threads", headers=peter).json()
        if t["title"].startswith("I am Anne")
    ]
    graph = client.app.state.graph  # type: ignore[attr-defined]
    state = client.portal.call(
        graph.aget_state, {"configurable": {"thread_id": thread}}
    )  # type: ignore[union-attr]
    profile = next(
        m.text for m in state.values["messages"] if isinstance(m, ToolMessage)
    )
    assert profile.startswith("You are Peter Bennett, a family member")


def test_telegram_sessions_stay_private(client: TestClient, test_password: str) -> None:
    peter = sign_in(client, PETER, test_password)
    anne = sign_in(client, ANNE, test_password)
    connect(client, peter, PETER_TG)
    bot_ask(client, PETER_TG, "What is Harold doing today?")
    peters = {t["thread_id"] for t in client.get("/threads", headers=peter).json()}
    annes = {t["thread_id"] for t in client.get("/threads", headers=anne).json()}
    assert peters and not peters & annes
    assert status_of(client, anne)["connected"] is False


def test_connecting_again_moves_the_link(
    client: TestClient, test_password: str
) -> None:
    peter = sign_in(client, PETER, test_password)
    anne = sign_in(client, ANNE, test_password)
    connect(client, peter, PETER_TG)
    bot_ask(client, PETER_TG, "What is Harold doing today?")

    # The same Telegram user connects to Anne's account: Peter's link is gone,
    # and Peter's session is not continued for Anne.
    connect(client, anne, PETER_TG)
    assert status_of(client, peter)["connected"] is False
    bot_ask(client, PETER_TG, "Hello")
    annes = [t["title"] for t in client.get("/threads", headers=anne).json()]
    assert "Hello" in annes and "What is Harold doing today?" not in annes

    # One account has one Telegram user: connecting another replaces it.
    connect(client, anne, ANNE_TG)
    assert bot_chat(client, PETER_TG, "hi").status_code == 403
    assert status_of(client, anne)["username"] == f"user{ANNE_TG}"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/telegram/connect"),
        ("POST", "/telegram/disconnect"),
        ("POST", "/telegram/new"),
        ("POST", "/telegram/messages"),
    ],
)
def test_bot_endpoints_need_the_bot_key(
    client: TestClient, test_password: str, method: str, path: str
) -> None:
    user_token = sign_in(client, PETER, test_password)
    body = {"telegram_user_id": PETER_TG, "code": "x", "content": "hi"}
    for headers in ({}, {"X-Bot-Key": "wrong-" + "k" * 40}, user_token):
        response = client.request(method, path, headers=headers, json=body)
        assert response.status_code == 401, (headers, response.text)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/me/telegram"),
        ("POST", "/me/telegram/code"),
        ("DELETE", "/me/telegram"),
    ],
)
def test_user_telegram_endpoints_need_a_sign_in(
    client: TestClient, method: str, path: str
) -> None:
    for headers in ({}, BOT):
        assert client.request(method, path, headers=headers).status_code == 401


def test_without_bot_settings_the_channel_is_off(
    make_client: Any, test_password: str
) -> None:
    client = make_client(telegram=False)
    peter = sign_in(client, PETER, test_password)
    assert client.post("/me/telegram/code", headers=peter).status_code == 503
    for path in ("/telegram/connect", "/telegram/messages"):
        response = client.post(path, headers=BOT, json={"telegram_user_id": PETER_TG})
        assert response.status_code == 404
