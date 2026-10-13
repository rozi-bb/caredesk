"""CareDesk chat UI, built with Chainlit (ADR-0024).

Run from this folder, so Chainlit reads this folder's `.env` and `.chainlit/`:
    cd src/ui && uv run chainlit run app.py

The UI holds no model keys and never touches the database. Sign-in, the
conversation list, and every answer come from the backend API.
"""

from __future__ import annotations

import os
from datetime import datetime

import chainlit as cl
import httpx

from ui.client import BackendClient, ConversationNotFound, SignInRequired, Thread

backend = BackendClient(os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"))

RESUME_LIMIT = 5
GREETING = (
    "Hi {name}. Ask me about schedules, activities, visits, billing, or the home's rules.\n\n"
    "**In an emergency, press the call bell, call the nurse station on extension 200, "
    "or call 911.**"
)
SIGNED_OUT = "Your sign-in has expired. Please sign out and sign in again."
UNREACHABLE = "CareDesk is not reachable right now. Please try again in a moment."


def _token() -> str:
    user = cl.user_session.get("user")
    token: str = user.metadata["token"] if user else ""
    return token


def _label(thread: Thread) -> str:
    # The backend sends UTC; show the time where the UI runs.
    started = datetime.fromisoformat(thread.created_at).astimezone()
    return f"{thread.title or 'Untitled'} · {started:%d %b %H:%M}"


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
    """Greet the user and offer their recent conversations."""
    user = cl.user_session.get("user")
    name = user.display_name if user and user.display_name else "there"
    try:
        recent = (await backend.threads(_token()))[:RESUME_LIMIT]
    except SignInRequired:
        await cl.Message(SIGNED_OUT).send()
        return
    except httpx.HTTPError:
        recent = []
    actions = [
        cl.Action(name="resume", payload={"thread_id": t.id}, label=_label(t))
        for t in recent
        if t.title
    ]
    text = GREETING.format(name=name)
    if actions:
        text += "\n\nOr continue an earlier conversation:"
    await cl.Message(text, actions=actions).send()


@cl.action_callback("resume")
async def resume(action: cl.Action) -> None:
    """Show an earlier conversation and continue it."""
    thread_id = action.payload["thread_id"]
    try:
        history = await backend.history(_token(), thread_id)
    except SignInRequired:
        await cl.Message(SIGNED_OUT).send()
        return
    except ConversationNotFound:
        await cl.Message("That conversation is no longer available.").send()
        return
    cl.user_session.set("thread_id", thread_id)
    for role, content in history:
        if role == "user":
            await cl.Message(content, author="You", type="user_message").send()
        else:
            await cl.Message(content).send()


@cl.on_message
async def answer(message: cl.Message) -> None:
    """Send the question to the backend and stream the answer back."""
    token = _token()
    reply = cl.Message("")
    try:
        thread_id = cl.user_session.get("thread_id")
        if not thread_id:
            thread_id = await backend.new_thread(token)
            cl.user_session.set("thread_id", thread_id)
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
