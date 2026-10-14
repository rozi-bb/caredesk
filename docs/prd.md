# CareDesk — Product Requirements

| | |
|---|---|
| Status | Draft |
| Release | Telegram channel (release 2 shipped as `v0.2.1`) |
| Last updated | 2026-10-14 |

## 1. Problem

Staff and families at a nursing home ask the same administrative questions every day: today's schedule, upcoming activities, visiting rules, what a resident is entitled to, where to file a complaint. Answers are scattered across schedules, the home's handbook, and federal regulations. Staff spend time repeating answers, and families wait for them.

## 2. Product

**CareDesk** is an administrative assistant for one fictional nursing home, *Evergreen Care Home*. It answers questions from the home's operational data and from its rules, in English.

Guiding principle: every answer can be traced to a source, and the assistant stops exactly at the medical line.

## 3. Users and permissions

| Role | Release | Can see | Cannot see |
|---|---|---|---|
| **Staff** | 1 | All residents' schedules, activities, visits, and incident records | Nothing restricted in release 1 |
| **Family member** | 1 | Schedules (including medication-round times, which carry no clinical detail), activities, and visits of their own linked resident. Billing only if their link grants financial access | Any other resident. Billing without financial access. Incident records |
| **Resident** | Later | Their own schedule, activities, and visits | Any other resident |

A resident can have several family members linked, each with their own access level. Example: four children are linked, and only one may see billing.

## 4. Example questions

**Staff**
- "Who has physiotherapy this afternoon?"
- "Which incidents are still waiting for follow-up?"
- "Can we put bed rails on Mr. Budi's bed to stop him falling?" (answered from the restraint regulations; the clinical decision stays with nurses)

**Family member**
- "What is my mother doing today?"
- "Can I visit outside visiting hours?"
- "My father's belongings went missing. How do I report it?"

## 5. Functional requirements — release 1

| ID | Requirement |
|---|---|
| F1 | **Conversation memory.** The assistant remembers earlier messages in the same conversation, including after a restart. |
| F2 | **Answers from operational data.** The assistant answers questions about schedules, activities, visits, incidents, and billing, limited to what the user's role may see (section 3). |
| F3 | **Answers from rules, with citations.** The assistant answers questions about resident rights, visiting, complaints, and restraint or abuse rules, and cites the F-tag or handbook section it used. |
| F4 | **Emergency handling.** Messages describing an emergency ("I fell", "she isn't waking up") get emergency instructions and contacts immediately, and create an incident record marked as needing action. |
| F5 | **Clinical questions declined.** Questions asking for diagnosis, medication, or treatment advice are declined politely and redirected to nursing staff. |

Release 1 is read-only. The incident record in F4 is the only data the assistant creates.

## 5a. Functional requirements — release 2

Release 2 adds no new assistant features. It turns release 1 into an app that people sign in to and use from a browser, running locally ([ADR-0019](adr/0019-release-2-thin-local-app.md)).

| ID | Requirement |
|---|---|
| F6 | **Sign in.** Staff and family members sign in with email and password. Their identity and role come from the account, never from the chat ([ADR-0022](adr/0022-accounts-created-by-the-home.md)). |
| F7 | **Accounts created by the home.** There is no self sign-up. Every account is linked to an existing staff or family record. |
| F8 | **Chat sessions in a sidebar, private per user.** Each chat is its own session, like a normal chat app. After signing in, users see their past sessions in a sidebar on the left, newest first, each titled by its first question, and can search them by title. They can start a new session, open an old one and continue where they left off (the assistant still remembers it, F1), and delete one. Sessions are kept after signing out and after a restart of the app. Each user sees only their own: no other account can list, open, continue, or delete them ([ADR-0025](adr/0025-sidebar-history-from-the-backend.md)). |
| F9 | **Chat in the browser.** A chat page where the answer appears as it is written. |
| F10 | **Usage recorded.** Each request is recorded per user (one row per request), so cost per user can be monitored later. Usage is never used to block a request. |

F1–F5 keep working unchanged, and F1 now also survives a restart of the app.

## 5b. Functional requirements — Telegram channel

Staff and family members can also chat with CareDesk from Telegram. The assistant, its rules, and the permissions are the same as in the browser ([ADR-0027](adr/0027-telegram-as-a-backend-client.md)).

| ID | Requirement |
|---|---|
| F11 | **Connect Telegram.** A signed-in user presses "Connect Telegram" (or types `/telegram`) in the browser and gets a link and a QR code to the bot. The link works once and expires after 10 minutes. Once connected, the browser shows which Telegram account is connected, so a wrong one can be spotted, with a "Disconnect Telegram" button. |
| F12 | **Chat in Telegram.** A connected user asks questions in a private chat with the bot and gets the same answers, with the same permissions, as in the browser. Who the user is comes only from the connection, never from what they type. |
| F13 | **Not connected, no data.** Anyone who has not connected gets only instructions to connect and the emergency contacts. |
| F14 | **One history.** Telegram continues the user's current session; `/new` starts a new one. Sessions from Telegram also appear in the browser sidebar. |
| F15 | **Disconnect.** Users can disconnect from the browser or with `/disconnect` in Telegram, for example after losing their phone. |

## 5c. Functional requirements — triage with Jev

Triage moves to Jev, a model built for fast decisions, with DeepSeek as the fallback ([ADR-0029](adr/0029-jev-triage-with-deepseek-fallback.md)). F4 and F5 do not change for the user.

| ID | Requirement |
|---|---|
| F16 | **No false alarms from single phrases.** Ordinary messages that only contain an emergency phrase, such as "I can't get up early for the 8am visit" or "What is the policy when a resident is choking?", are not handled as emergencies. |
| F17 | **When a message cannot be checked.** If triage cannot decide (both Jev and the fallback fail), the user gets a fixed reply: the message could not be checked, the emergency contacts, and a request to try again. No incident is recorded and the question is not answered. |

## 6. Product rules

These hold in every release. They must hold no matter what the user types, including attempts to talk the assistant out of them.

1. **No diagnosis and no medication or treatment advice.**
2. **No information outside the user's permissions** (section 3).
3. **No fabricated answers.** If no source supports an answer, the assistant says it does not know.
4. **Emergencies come first,** and nothing may delay or block an emergency message.
5. **No real personal data.** All resident, family, and staff data is synthetic.

## 7. Data

| Kind | Content | Source |
|---|---|---|
| Rules | 14 F-tags covering resident rights, visiting and family notification, complaints, restraint and abuse protection, and bed rails (list in [ADR-0005](adr/0005-narrow-the-rules-corpus.md)) | CMS State Operations Manual, Appendix PP (public domain) |
| Handbook | Evergreen's own policies, written to be consistent with the F-tags above | Written for this project |
| Operational | Residents, family links, staff, schedules, activities, visits, incidents, billing | Synthetic, generated with a fixed seed |

The F-tags are chosen from real questions in section 4, not the other way around. Clinical regulations and building or fire-safety regulations are deliberately excluded.

The synthetic data deliberately includes hard cases: residents with near-identical names, and families where members have different access levels.

From release 2, every staff and family record also has a synthetic account (email and password) for signing in. Demo passwords are generated by the seed script and never committed.

## 8. Success criteria

Release 1 is done when evaluation shows:

| Category | Question | Target |
|---|---|---|
| Correctness | Does the answer match the data? | 90% |
| Groundedness | Is every rule-based answer supported by the cited source? | Right source 90%; no invented source 100%; honest "I don't know" 90% |
| Safety | Are clinical questions declined and emergencies handled? | 100% |
| Access control | Do attempts to reach another resident's data fail? | 100% |

Safety, access control, and invented sources are pass/fail: a single failure blocks the release. The other targets allow one miss in ten, because answers vary slightly between runs ([ADR-0018](adr/0018-release-targets.md)).

Release 2 is done when:

- The four evaluations above still meet their targets, now running against the release 2 database.
- Business-flow tests pass: sign-in works, a wrong password is rejected, a chat request is recorded as usage, and after signing in again a user finds their earlier sessions in the sidebar and can continue them.
- Security tests pass, all pass/fail: a user cannot see, open, continue, or delete another user's session, no endpoint works without signing in, the model provider's API key never reaches the browser, and attempts to talk the assistant out of its rules fail.

The Telegram channel is done when:

- Business-flow tests pass: connecting works from the link, a connected user gets answers, `/new` and disconnecting work, and Telegram sessions appear in the browser sidebar.
- Security tests pass, all pass/fail: a user who has not connected gets no data, a used or expired link is refused, a connected user sees only their own data, the bot answers nothing in group chats, and the bot token and backend key never reach a user.

Triage with Jev is done when:

- The safety evaluation is 100% with Jev, and also with the fallback classifier alone.
- The safety evaluation includes look-alike ordinary messages (F16), and none of them is handled as an emergency.
- Unit tests show all three paths: Jev decides, the fallback decides, and both fail with the fixed reply (F17).
- The other three evaluations still meet their targets.

## 9. Out of scope

- Resident access
- Write actions such as booking a visit, and human confirmation for them
- Data entry forms
- Self sign-up and password reset by email
- Running on the internet: CareDesk runs locally only and is never deployed ([ADR-0026](adr/0026-no-deployment.md))
- Notifications outside the app (email, messaging). The Telegram bot only answers; it never writes first
- WhatsApp, and Telegram group chats
- Usage limits and payments. The home pays per use; there is never a hard limit, because a limit could block an emergency message ([ADR-0009](adr/0009-no-hard-usage-limits.md))
- More than one nursing home

## 10. Open questions

| Question | Needed by |
|---|---|
| The chat shows 👍 / 👎 under each answer, but they are not stored yet. Store them (for example on the answer's LangSmith trace) or hide them? | Next UI change |
