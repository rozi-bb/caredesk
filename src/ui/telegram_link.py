"""What the chat shows for connecting Telegram (ADR-0027).

Kept apart from `app.py` so the texts and the QR code can be tested without
a running Chainlit session.
"""

from __future__ import annotations

import io

import segno

from ui.client import ConnectLink, TelegramStatus

COMMAND = "telegram"
CONNECT = "connect_telegram"
CHECK = "check_telegram"
DISCONNECT = "disconnect_telegram"


def status_text(status: TelegramStatus) -> str:
    """Return one line saying whether the account is connected, and to whom."""
    if not status.connected:
        return "Telegram is not connected."
    who = f"@{status.username}" if status.username else "a Telegram account"
    # Showing who is connected lets a user spot a link that reached the wrong person.
    return f"Telegram is connected to {who}. Not you? Disconnect it."


def link_text(link: ConnectLink) -> str:
    """Return how to use the connect link."""
    return (
        "Scan the QR code with your phone, or open this link where you use Telegram, "
        f"then press **Start**:\n\n{link.link}\n\n"
        "The link works once and expires in 10 minutes. Do not share it: "
        "whoever opens it can chat as you."
    )


NOT_YET = (
    "Not connected yet. Open the link in Telegram and press **Start**, "
    "then check again."
)
DISCONNECTED = "Telegram is disconnected. Messages from it are no longer answered."
UNAVAILABLE = "Telegram is not set up for CareDesk yet."


def qr_png(link: str) -> bytes:
    """Return the link as a QR code image, for opening it on a phone."""
    out = io.BytesIO()
    segno.make(link, error="m").save(out, kind="png", scale=6, border=2)
    return out.getvalue()
