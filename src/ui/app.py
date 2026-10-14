"""CareDesk chat UI, built with Chainlit (ADR-0024, ADR-0025, ADR-0027).

Run from this folder, so Chainlit reads this folder's `.env` and `.chainlit/`:
    cd src/ui && uv run chainlit run app.py --port 8001

The UI holds no model keys and never touches the database. Sign-in, the
sidebar of past conversations, every answer, and the Telegram connection come
from the backend API.
"""

from __future__ import annotations

import os

import chainlit as cl
import httpx
from chainlit.types import ThreadDict

from ui import telegram_link as tg
from ui.client import (
    BackendClient,
    ConversationNotFound,
    SignInRequired,
    TelegramStatus,
    TelegramUnavailable,
    ThreadIdTaken,
)
from ui.data_layer import BackendDataLayer

backend = BackendClient(os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"))
history = BackendDataLayer(backend)

# The topics and emergency contacts come from the backend (GET /texts), so the
# chat and the Telegram bot always show the same numbers.
GREETING = "Hi {name}. {topics}\n\n**{emergency_notice}**"
# Only when the backend cannot be reached: the emergency line must still show.
OFFLINE_GREETING = (
    "Hi {name}. CareDesk is not reachable right now. Please try again in a moment.\n\n"
    "**In an emergency, press the call bell or call 911.**"
)
SIGNED_OUT = "Your sign-in has expired. Please sign out and sign in again."
UNREACHABLE = "CareDesk is not reachable right now. Please try again in a moment."


@cl.data_layer
def get_data_layer() -> BackendDataLayer:
    """Give Chainlit the sidebar history, read from the backend."""
    return history


def _user() -> cl.User | None:
    user: cl.User | None = cl.user_session.get("user")
    return user


def _token() -> str:
    user = _user()
    return (history.token_for(user.identifier) if user else None) or ""


@cl.password_auth_callback
async def sign_in(email: str, password: str) -> cl.User | None:
    """Check the email and password with the backend."""
    try:
        token = await backend.login(email, password)
        if token is None:
            return None
        me = await backend.profile(token)
    except httpx.HTTPError:
        return None
    return cl.User(
        identifier=me.email,
        display_name=me.name,
        metadata={"role": me.role, "token": token},
    )


@cl.on_chat_start
async def start() -> None:
    """Greet the user and offer Telegram. Past conversations are in the sidebar."""
    user = _user()
    name = user.display_name if user and user.display_name else "there"
    try:
        texts = await backend.texts()
        text = GREETING.format(
            name=name, topics=texts.topics, emergency_notice=texts.emergency_notice
        )
    except httpx.HTTPError:
        text = OFFLINE_GREETING.format(name=name)
    status = await _telegram_status()
    actions: list[cl.Action] = []
    if status and status.available:
        await _offer_telegram_command()
        actions = _telegram_actions(status)
        if status.connected:
            text += "\n\n" + tg.status_text(status)
    await cl.Message(text, actions=actions).send()


@cl.on_chat_resume
async def resume(thread: ThreadDict) -> None:
    """Continue a conversation picked from the sidebar.

    Chainlit only gets here after the data layer confirmed, with the backend,
    that the signed-in user owns the thread.
    """
    cl.user_session.set("thread_id", thread["id"])
    status = await _telegram_status()
    if status and status.available:
        await _offer_telegram_command()


# ---------- Telegram connection (ADR-0027) ----------


async def _telegram_status() -> TelegramStatus | None:
    try:
        return await backend.telegram_status(_token())
    except (SignInRequired, httpx.HTTPError):
        return None


async def _offer_telegram_command() -> None:
    await cl.context.emitter.set_commands(
        [
            {
                "id": tg.COMMAND,
                "description": "Connect or check Telegram",
                "icon": "send",
                "button": False,
                "persistent": False,
                "selected": False,
            }
        ]
    )


def _connect_button(label: str = "Connect Telegram") -> cl.Action:
    return cl.Action(name=tg.CONNECT, payload={}, label=label, icon="send")


def _telegram_actions(status: TelegramStatus) -> list[cl.Action]:
    if status.connected:
        return [
            cl.Action(
                name=tg.DISCONNECT,
                payload={},
                label="Disconnect Telegram",
                icon="unlink",
            )
        ]
    return [_connect_button()]


async def _send_connect_link() -> None:
    """Show a new one-time link and its QR code. The message never reaches the agent."""
    try:
        link = await backend.telegram_link(_token())
    except TelegramUnavailable:
        await cl.Message(tg.UNAVAILABLE).send()
        return
    except SignInRequired:
        await cl.Message(SIGNED_OUT).send()
        return
    except httpx.HTTPError:
        await cl.Message(UNREACHABLE).send()
        return
    qr = cl.Image(
        name="Telegram connect code", content=tg.qr_png(link.link), size="small"
    )
    check = cl.Action(
        name=tg.CHECK, payload={}, label="Check connection", icon="refresh-cw"
    )
    await cl.Message(tg.link_text(link), elements=[qr], actions=[check]).send()


async def _send_telegram_status(after_check: bool = False) -> None:
    status = await _telegram_status()
    if status is None:
        await cl.Message(UNREACHABLE).send()
    elif not status.available:
        await cl.Message(tg.UNAVAILABLE).send()
    elif status.connected:
        await cl.Message(
            tg.status_text(status), actions=_telegram_actions(status)
        ).send()
    elif after_check:
        check = cl.Action(
            name=tg.CHECK, payload={}, label="Check again", icon="refresh-cw"
        )
        await cl.Message(
            tg.NOT_YET, actions=[check, _connect_button("New link")]
        ).send()
    else:
        await _send_connect_link()


@cl.action_callback(tg.CONNECT)
async def on_connect(action: cl.Action) -> None:
    """Show a connect link; any earlier link stops working."""
    await action.remove()
    await _send_connect_link()


@cl.action_callback(tg.CHECK)
async def on_check(action: cl.Action) -> None:
    """Say whether the Telegram account is connected now."""
    await action.remove()
    await _send_telegram_status(after_check=True)


@cl.action_callback(tg.DISCONNECT)
async def on_disconnect(action: cl.Action) -> None:
    """Disconnect Telegram; its messages stop being answered at once."""
    await action.remove()
    try:
        await backend.disconnect_telegram(_token())
    except SignInRequired:
        await cl.Message(SIGNED_OUT).send()
        return
    except httpx.HTTPError:
        await cl.Message(UNREACHABLE).send()
        return
    await cl.Message(tg.DISCONNECTED, actions=[_connect_button()]).send()


async def _thread_for(token: str) -> str:
    """Return this chat's backend thread, creating it on the first message."""
    thread_id: str | None = cl.user_session.get("thread_id")
    if thread_id:
        return thread_id
    # Use Chainlit's own id, so the sidebar and the backend name the thread alike.
    try:
        thread_id = await backend.new_thread(token, cl.context.session.thread_id)
    except ThreadIdTaken:
        thread_id = await backend.new_thread(token)
    user = _user()
    if user:
        history.remember_thread(thread_id, user.identifier, None)
    cl.user_session.set("thread_id", thread_id)
    return thread_id


@cl.on_message
async def answer(message: cl.Message) -> None:
    """Send the question to the backend and stream the answer back."""
    if (
        message.command == tg.COMMAND
        or message.content.strip().lower() == f"/{tg.COMMAND}"
    ):
        await _send_telegram_status()
        return
    token = _token()
    reply = cl.Message("")
    try:
        thread_id = await _thread_for(token)
        async for event, data in backend.ask(token, thread_id, message.content):
            if event == "token":
                await reply.stream_token(data["text"])
            elif event == "error":
                await reply.stream_token(data["message"])
    except SignInRequired:
        await reply.stream_token(SIGNED_OUT)
    except ConversationNotFound:
        cl.user_session.set("thread_id", None)
        await reply.stream_token(
            "That conversation is no longer available. Please ask again."
        )
    except httpx.HTTPError:
        await reply.stream_token(UNREACHABLE)
    await reply.send()
