# ADR-0028: Telegram answers stream as message drafts

- Status: Accepted
- Date: 2026-10-14
- Replaces the "answers are sent whole" part of [ADR-0027](0027-telegram-as-a-backend-client.md)

## Context

In the browser, the answer appears as it is written. In Telegram it arrived only when complete, after a "typing…" indicator, which feels slow for long answers. The project owner asked for streaming in Telegram too. The backend already streams every answer; only the bot waited for the end.

## Decision

- The bot reads the backend's stream piece by piece and shows the answer so far as a Telegram **message draft** (`sendMessageDraft`), a temporary preview in private chats that Telegram animates between updates.
- The draft is updated at most once a second, to stay within Telegram's rate limits.
- When the answer is complete, the bot sends it as a normal message, as before. Only that message stays in the chat; the draft is just a preview.
- An answer longer than one Telegram message is split as before: each finished part is sent as a message, and the draft continues with the rest.
- Streaming is best effort. If a draft fails, the bot stops drafting for that answer and the final message is still sent. Fixed replies, such as the emergency reply, come in one piece and are sent at once.
- Each user's messages are still handled in order, and users are still served side by side.

## Alternatives considered

- **Send a message, then edit it as the answer grows**: works in every Telegram version, but each edit counts against rate limits, and the chat shows an edited message.
- **Keep sending whole answers**: simplest, but long answers feel slow.

## Consequences

- Telegram answers feel as quick as the browser's.
- The bot keeps a little more state per answer: the draft id, how much was sent, and when the draft was last updated.
- Drafts need a recent Telegram app; older apps show the final message only, as before.
