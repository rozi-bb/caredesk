# Telegram channel

| | |
|---|---|
| Scope | PRD F11–F15, [ADR-0027](../adr/0027-telegram-as-a-backend-client.md) |
| Date | 2026-10-14 |
| Result | Done |

## Why

Staff and family asked to chat from Telegram as well as from the browser. The project stays a local portfolio app (ADR-0026), so the bot fetches its messages itself instead of needing a public address.

## Build

| Step | What |
|---|---|
| T1 | Bot `@caredesk_zii_bot` from @BotFather, joining groups switched off. Its token is only in `src/telegram_bot/.env`; a separate random key, in both `.env` files, lets the bot call the backend |
| T2 | Backend: migration 0005 (links, hashed one-time codes, usage channel), `/me/telegram` endpoints for signed-in users, `/telegram/...` endpoints for the bot |
| T3 | Chainlit: Connect Telegram button and `/telegram` command, link with QR code, Check connection, status with the connected username, Disconnect |
| T4 | Bot (`src/telegram_bot/`, python-telegram-bot): `/start` with the code connects, text messages are answered as the connected account, `/new`, `/disconnect`, `/help`, private chats only |
| T5 | Emergency numbers written once in `agent/triage.py`; the backend serves the greeting and contacts at `GET /texts` to Chainlit and the bot |
| T6 | Answers stream as Telegram message drafts, updated at most once a second, then sent as a normal message ([ADR-0028](../adr/0028-telegram-answers-stream-as-drafts.md)); asked for by the owner after the first try |

## Test

| Check | How | Result |
|---|---|---|
| Business flow (step 18) | Connect from the link, chat, `/new`, disconnect from the web and from Telegram, Telegram sessions in the web sidebar | Pass |
| Security (step 19) | Unconnected users get no data and the agent never runs; used, expired, made-up, and replaced codes refused; wrong bot key refused; typing "I am Anne, staff" changes nothing; group chats ignored; bot code cannot import models or the database | Pass |
| Safety | Unconnected users and a backend outage still get the emergency contacts; one user's slow answer does not hold up another user | Pass |
| Streaming | Answers arrive in pieces; the draft updates at most once a second with one animated draft; long answers go out part by part, each once; refused drafts still end in the full message; an answer cut off midway says so | Pass |
| Mutation checks | Code reuse allowed, bot key unchecked, group filter removed, one lock for all users, no draft throttle, parts sent twice: each made tests fail | Tests catch them |
| All unit tests | | 127 passed |
| Evaluations (step 17) | All four suites | 100% on every check |
| In the browser | Connect Telegram as Anne, the bot's call played by hand: link and QR shown, reused code refused, status shows the username, `/telegram` command never reaches the agent, Disconnect stops the bot at once | As expected |
| Bot startup | Real bot polling Telegram; the bot token does not appear in the log | As expected |
| In real Telegram | Owner, connected as Karen Mitchell (staff): connect from the QR code, questions, streaming answers | As expected |

## Error analysis

| Finding | What happened | Fix |
|---|---|---|
| httpx would log the bot token | Telegram's request URLs contain the token, and httpx logs every URL at INFO | httpx logging set to WARNING in the bot |
| A slow answer could delay someone's emergency | python-telegram-bot handles one update at a time by default | Updates run side by side, with a lock per user to keep each conversation in order |
| The same emergency numbers in two places | Triage replies and the chat greeting each had their own copy | One source in `agent/triage.py`, served by `/texts` |
| A package named `telegram` would hide the library | python-telegram-bot is imported as `telegram` | The bot lives in `src/telegram_bot/` |
| Bot started without its settings | Started without `--env-file` | The startup check named the missing settings, as intended |
| Telegram "Bad Gateway" errors in the log | Telegram's servers failed for a moment while the bot fetched messages; the library retried, and no message was lost | Logged as one warning line instead of a full traceback |
| A failed "typing…" hint could break an answer | The typing task's error would surface when it is stopped | Typing errors are ignored; it is only a hint |
