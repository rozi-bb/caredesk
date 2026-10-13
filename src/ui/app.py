"""CareDesk chat UI, built with Chainlit (ADR-0024, ADR-0025).

Run from this folder, so Chainlit reads this folder's `.env` and `.chainlit/`:
    cd src/ui && uv run chainlit run app.py --port 8001

The UI holds no model keys and never touches the database. Sign-in, the
sidebar of past conversations, and every answer come from the backend API.
"""

from __future__ import annotations

import os

import chainlit as cl
import httpx
from chainlit.types import ThreadDict

from ui.client import BackendClient, ConversationNotFound, SignInRequired, ThreadIdTaken
from ui.data_layer import BackendDataLayer

backend = BackendClient(os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"))
history = BackendDataLayer(backend)

GREETING = (
    "Hi {name}. Ask me about schedules, activities, visits, billing, or the home's rules.\n\n"
    "**In an emergency, press the call bell, call the nurse station on extension 200, "
    "or call 911.**"
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
    """Greet the user. Past conversations are in the sidebar."""
    user = _user()
    name = user.display_name if user and user.display_name else "there"
    await cl.Message(GREETING.format(name=name)).send()


@cl.on_chat_resume
async def resume(thread: ThreadDict) -> None:
    """Continue a conversation picked from the sidebar.

    Chainlit only gets here after the data layer confirmed, with the backend,
    that the signed-in user owns the thread.
    """
    cl.user_session.set("thread_id", thread["id"])


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
