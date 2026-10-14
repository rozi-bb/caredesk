"""CareDesk's Telegram bot: a thin client of the backend (ADR-0027, ADR-0028).

Run from the project root, with the bot's own environment file:
    uv run --env-file src/telegram_bot/.env python -m telegram_bot

The bot fetches new messages from Telegram itself (polling), so it runs on
this machine without a public address. It holds no model keys and never
touches the database; it only relays messages to the backend.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

from telegram import BotCommand, Chat, Message, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, NetworkError, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegram_bot import format as tg_format
from telegram_bot.backend import BotBackend
from telegram_bot.relay import CUT_OFF, TEXT_ONLY, UNREACHABLE, Relay
from telegram_bot.streaming import AnswerStream

log = logging.getLogger("telegram_bot")

# The bot answers only in one-to-one chats: in a group, other members would
# read a resident's data.
PRIVATE = filters.ChatType.PRIVATE
COMMANDS = [
    BotCommand("new", "Start a new conversation"),
    BotCommand("disconnect", "Disconnect this Telegram from CareDesk"),
    BotCommand("help", "What I can do"),
]
TYPING_EVERY = 4.0  # Telegram shows "typing…" for about 5 seconds per call


async def _keep_typing(chat: Chat) -> None:
    while True:
        # Only a hint to the user: a failed one must not break the answer.
        with contextlib.suppress(TelegramError):
            await chat.send_action(ChatAction.TYPING)
        await asyncio.sleep(TYPING_EVERY)


async def _send(message: Message, piece: str) -> None:
    try:
        await message.reply_text(tg_format.to_html(piece), parse_mode=ParseMode.HTML)
    except BadRequest:
        # Telegram rejected the converted HTML; plain text always goes through.
        await message.reply_text(piece)


async def _reply(update: Update, markdown: str) -> None:
    message = update.effective_message
    if message is None:
        return
    for piece in tg_format.split(markdown):
        await _send(message, piece)


async def _stop(task: asyncio.Task[None]) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def _user_id(update: Update) -> int:
    user = update.effective_user
    assert user is not None  # every private message has a sender
    return user.id


def build(token: str, relay: Relay) -> Application:  # type: ignore[type-arg]
    """Wire Telegram commands and messages to the relay."""

    async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        code = context.args[0] if context.args else None
        user = update.effective_user
        username = user.username if user else None
        await _reply(update, await relay.start(_user_id(update), username, code))

    async def on_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _reply(update, await relay.help(_user_id(update)))

    async def on_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _reply(update, await relay.new(_user_id(update)))

    async def on_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _reply(update, await relay.disconnect(_user_id(update)))

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message, chat = update.effective_message, update.effective_chat
        if message is None or chat is None or message.text is None:
            return

        async def draft(draft_id: int, piece: str) -> None:
            try:
                await context.bot.send_message_draft(
                    chat.id,
                    draft_id,
                    tg_format.to_html(piece),
                    parse_mode=ParseMode.HTML,
                )
            except BadRequest:
                await context.bot.send_message_draft(chat.id, draft_id, piece)

        stream = AnswerStream(draft, lambda piece: _send(message, piece))
        typing = asyncio.create_task(_keep_typing(chat))
        answer = ""
        try:
            async for piece in relay.stream(_user_id(update), message.text):
                if not answer:
                    await _stop(typing)  # the draft shows progress from here
                answer += piece
                await stream.update(answer)
        finally:
            await _stop(typing)
        await stream.finish(answer or CUT_OFF)

    async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _reply(update, TEXT_ONLY)

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update is None and isinstance(context.error, NetworkError):
            # Fetching messages from Telegram failed for a moment; the library
            # retries, and unfetched messages wait on Telegram's side.
            log.warning("Telegram unreachable, retrying: %s", context.error)
            return
        log.error("Update failed", exc_info=context.error)
        if isinstance(update, Update):
            await _reply(update, UNREACHABLE)

    async def post_init(app: Application) -> None:  # type: ignore[type-arg]
        await app.bot.set_my_commands(COMMANDS)

    app = (
        Application.builder()
        .token(token)
        # Users are served side by side, so one slow answer never holds up
        # someone else's emergency; the relay keeps each user's own messages in order.
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", on_start, filters=PRIVATE))
    app.add_handler(CommandHandler("help", on_help, filters=PRIVATE))
    app.add_handler(CommandHandler("new", on_new, filters=PRIVATE))
    app.add_handler(CommandHandler("disconnect", on_disconnect, filters=PRIVATE))
    app.add_handler(MessageHandler(PRIVATE & filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(
        MessageHandler(PRIVATE & ~filters.TEXT & ~filters.COMMAND, on_other)
    )
    app.add_error_handler(on_error)
    return app


def main() -> None:
    """Start the bot with settings from the environment."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    # httpx logs every request URL, and Telegram's URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    missing = [
        name
        for name in ("BACKEND_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(
            f"Set {', '.join(missing)} in src/telegram_bot/.env (see .env.example)."
        )
    relay = Relay(BotBackend(os.environ["BACKEND_URL"], os.environ["TELEGRAM_BOT_KEY"]))
    app = build(os.environ["TELEGRAM_BOT_TOKEN"], relay)
    log.info("CareDesk bot is running. Press Ctrl+C to stop.")
    # Only new messages: edited messages are not answered again.
    app.run_polling(allowed_updates=["message"])
