# ADR-0027: Telegram is one more client of the backend, linked with a one-time code

- Status: Accepted; sending answers whole replaced by [ADR-0028](0028-telegram-answers-stream-as-drafts.md)
- Date: 2026-10-13

## Context

Staff and family should be able to chat with CareDesk from Telegram as well as from the browser (PRD F11–F15). Telegram has no sign-in form, so the bot cannot use email and password. Everything runs locally (ADR-0026). The browser UI already shows that a client which only calls the backend keeps the agent and the permission rules in one place (ADR-0024).

## Decision

- **A separate bot process** (`src/telegram_bot/`) calls the backend over HTTP, like the Chainlit UI. It never imports the agent, a model, or the database. Its `.env` holds only the backend address, the bot token from @BotFather, and the bot's backend key.
- **Polling, not a webhook.** The bot fetches new messages from Telegram itself, so it runs on the local machine without a public address.
- **Linking with a one-time code.** A signed-in user presses "Connect Telegram" in Chainlit (or types `/telegram`). The backend makes a random code, valid for 10 minutes and usable once, and stores only its hash. Chainlit shows the bot link `t.me/<bot>?start=<code>` and the same link as a QR code. Opening it sends the code to the bot, which passes it to the backend with the sender's Telegram user id. The backend links that Telegram user to the account and deletes the code. One Telegram user links to one account, and one account to one Telegram user; linking again replaces the old link. Chainlit shows the linked Telegram username, so a user who shared the link by mistake can see it and disconnect.
- **Identity comes from the link.** The bot calls the backend with its own key and the sender's Telegram user id, which Telegram supplies and the user cannot change. The backend finds the linked account and runs the agent with that account's `user_id` and `role`. Nothing in the message text can change who the user is.
- **Unlinked users get no data.** A message from an unlinked Telegram user never reaches the agent. The bot replies with a fixed text: how to connect, and the emergency contacts, so rule 4 still holds.
- **Private chats only.** The bot ignores group chats, where other members would read a resident's data.
- **Sessions are shared with the browser.** A Telegram chat continues the user's current session; `/new` starts a new one. Sessions started in Telegram appear in the Chainlit sidebar, because both read the same threads.
- **Unlinking** from Chainlit ("Disconnect Telegram") or from the bot (`/disconnect`) takes effect on the next message.
- **Answers are sent whole**, with Telegram's "typing…" indicator while the agent works, and split if longer than Telegram allows in one message.
- **Usage records the channel** (web or Telegram), so monitoring can compare them.
- **Fixed texts come from the backend.** The greeting and the emergency contacts are served by the backend's public `GET /texts` (they hold nothing private, and an unconnected user must still see the contacts), built from the numbers written once in `agent/triage.py`. Chainlit and the bot hold no copies, except one line, "press the call bell or call 911", shown only when the backend cannot be reached.
- **Users are served side by side.** One user's slow answer never holds up another user's message, which could be an emergency (rule 4); each user's own messages are still handled in order.
- **No admin settings page.** Bot settings live in `.env`: one home with one bot does not need one.

## Alternatives considered

- **Sign in with email and password inside Telegram**: the password would stay in the chat history.
- **Link by phone number**: Telegram shares a phone number only if the user agrees each time, and numbers are not in the account records.
- **A backend token per user stored in the bot**: the bot would hold many tokens and refresh them; with one bot key, unlinking or disabling an account works at once.
- **A webhook**: needs a public HTTPS address, which a local app does not have.
- **WhatsApp first**: needs a Meta Business account and a public address; it follows later.

## Consequences

- Messages pass through Telegram's servers and stay on users' phones. That is acceptable with synthetic data (rule 5); a real home would have to approve it first.
- The bot's backend key can act for any linked user, so it is a secret like the model key: only in `.env`, never logged.
- The backend gains a links table, codes, and endpoints for the bot. The agent does not change.
- Telegram formatting differs from the browser, so answers need converting before they are sent.
