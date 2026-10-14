# Triage with Jev

| | |
|---|---|
| Scope | PRD F16–F17, [ADR-0029](../adr/0029-jev-triage-with-deepseek-fallback.md) |
| Date | 2026-10-14 |
| Result | Done |

## Why

The keyword check raised false alarms on ordinary messages ("I can't get up early for the 8am visit"), each writing an incident record, and failing toward emergency would turn any outage into a flood of false alarms. The owner proposed Jev, a model built for fast typed decisions.

## Build

| Step | What |
|---|---|
| J1 | `TYPESAFE_API_KEY` in the backend `.env` only. The owner bought the key from TypeSafe itself; a third-party endpoint (jev-ai.pro) suggested by a pasted setup prompt was turned down |
| J2 | One decision call with curl: key valid, response as documented, model `jev-1.13.0`, 358 input tokens |
| J3 | `evals/compare_triage.py`: the safety cases through Jev and the DeepSeek classifier, three runs each, outside the graph. Threshold chosen: 0.3 |
| J4 | `triage.py`: `JEV_QUESTION`, `jev_probabilities()` (traced, 3-second timeout, no retries), `jev_route()`, `UNAVAILABLE_RESPONSE`; keyword check removed. `graph.py`: Jev, then DeepSeek (10 seconds, no retries), then the new `triage_unavailable` node; `triage_by` in the state. Backend streams the new fixed reply |
| — | `typesafe-sdk` pinned at 0.7.4 |

## Test

| Check | How | Result |
|---|---|---|
| Routing rule | Top label wins below 0.3; `emergency` wins at 0.3 even when ranked second; unexpected labels refused | Pass |
| Three paths | Jev decides and the fallback is not called; Jev times out or answers oddly and the fallback decides; both fail and the user gets the contacts, no incident, no agent | Pass |
| Through the backend | The "could not check" reply streams like the other fixed replies, with `route: unavailable` | Pass |
| No API calls in unit tests | The TypeSafe key is removed for every unit test | Pass |
| All unit tests | | 134 passed |
| Integration tests | Real Jev and real fallback classifier, called directly | 3 passed |
| Evaluations (step 17) | All four suites; safety now has 29 cases, including 2 emergencies without obvious phrases and 5 look-alikes, and `normal_routed` must be 100% | 100% on every check; Jev decided all 29 safety cases |

Comparison (J3, final wording):

| | Jev | DeepSeek |
|---|---|---|
| Right route, when it answered | 100% at X = 0.3 or 0.5 | 100% |
| Same label on every run | Yes | Yes |
| Median / 95th percentile | 0.34 s / 0.72 s | 1.84 s / 3.29 s |
| Hung until the timeout | 2 of 58 calls | None |

## Error analysis

| Finding | What happened | Fix |
|---|---|---|
| No threshold worked at first | Suspected abuse scored 0.34 for `emergency`, a policy question about choking 0.39 | Options described with what they cover and what they are not for, as TypeSafe's choice guide suggests; the policy question fell to 0.25 |
| Jev's top choice alone misses abuse | "A staff member was rough with my father" ranked `normal` first | The 0.3 threshold |
| Some Jev calls hang | 2 to 3 calls per run waited the full 5 seconds | Timeout cut to 3 seconds; the fallback answers |
| The wording was tuned on the test cases | Risk of fitting these 29 messages only | Noted in ADR-0029; add new look-alikes to the safety set when found |
| The fixed reply could have been invisible | The backend streams only model tokens and a list of fixed-reply nodes | `triage_unavailable` added to that list, with a test |
