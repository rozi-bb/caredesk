# ADR-0029: Jev triages every message, DeepSeek is the fallback, and a fixed reply covers both failing

- Status: Accepted. Supersedes [ADR-0016](0016-emergency-keyword-precheck.md) and the "fail toward emergency" part of [ADR-0006](0006-triage-first-fail-safe.md)
- Date: 2026-10-14

## Context

Triage was a keyword check followed by a `deepseek-flash` classifier, and any classifier failure was handled as an emergency (ADR-0006, ADR-0016).

Two problems showed up:

- The keyword check raised false alarms on ordinary messages. "I can't get up early for the 8am visit", "What is the policy when a resident is choking?" and "is the chest pains clinic on Monday?" all matched it, and each false alarm wrote an incident record.
- Failing toward emergency turns every outage into false alarms. If the provider is down or the balance runs out, every message gets the emergency reply and creates an incident.

Jev, from TypeSafe AI, is a model built for this kind of decision. It does not write text: it picks one option from a list we define and returns a probability for each option.

Before deciding, Jev and the DeepSeek classifier were compared on the 29 safety cases, three runs each, outside the graph (`evals/compare_triage.py`, roadmap step J3):

| | Jev | DeepSeek |
|---|---|---|
| Right route, when it answered | 100% with the threshold below | 100% |
| Same label on every run | Yes | Yes |
| Median / 95th percentile response time | 0.34 s / 0.72 s | 1.84 s / 3.29 s |
| Calls that hung until the timeout | 2 to 3 per 60 to 90 | None |

With the first wording of the options, no threshold separated two cases: suspected abuse ("a staff member was rough with my father") scored 0.34 for `emergency`, below a policy question about choking at 0.39. Spelling out abuse under `emergency`, and policy questions under what it is not for, brought the policy question down to 0.25. These cases were also the ones the wording was tuned on, so new look-alikes should be added to the safety set when they are found.

## Decision

- **No keyword check.** Every message goes to a classifier.
- **Jev first.** A `choice` question with the options `emergency`, `clinical`, and `normal`, each with what it covers and what it is not for. Model `jev-latest`, through TypeSafe's own API (`https://api.typesafe.ai`) with the official Python SDK (`typesafe-sdk`, pinned). Timeout 3 seconds, no retries: a hung call is cut short, a retry would double the wait, and an unclear outcome could be billed twice.
- **Lean toward emergency.** If Jev gives `emergency` a probability of 0.3 or more, the message is an emergency even when another option scores higher. 0.3 sits above every ordinary look-alike (at most 0.25) and below suspected abuse. Labels other than the three expected ones count as a Jev failure.
- **DeepSeek as fallback.** If Jev fails (401, 402 out of balance, 429, 529, timeout, no connection, or an unexpected answer), the `deepseek-flash` classifier labels the message instead, with a 10-second timeout and no retries.
- **A fixed reply if both fail.** A new route, `unavailable`, goes to a new node, `triage_unavailable`, which sends this fixed text and nothing else:

  > I can't check your message right now because part of our system is unavailable.
  > If someone is in danger, press the call bell, call the nurse station on extension 200 (staffed 24 hours), or call 911.
  > For anything else, please try again in a few minutes.

  The contacts come from the same constants as the emergency reply. No incident is written and the agent does not run. Both failures are logged.
- **Traced.** Jev is not a LangChain model, so its call is wrapped with LangSmith's `traceable`. The graph's state records which classifier decided (`triage_by`: `jev`, `deepseek`, or empty).
- **Key on the server only.** `TYPESAFE_API_KEY` lives in the backend's `.env`, never in the UI or bot `.env`. Unit tests remove it, so they never call TypeSafe.

## Alternatives considered

- **Keep the keyword check, tightened**: fewer false alarms, still instant and working offline, but every new phrasing needs a new pattern and the false alarms never fully go away.
- **Match whole sentences instead of keywords**: people in an emergency write in many ways, so whole sentences would almost never match.
- **Jev only, failing toward emergency**: an outage or an empty balance would turn every message into a false alarm with an incident record.
- **Jev only, failing toward a normal answer**: an outage would silently remove the safety net. This breaks product rule 4.
- **DeepSeek only, as before**: as accurate on our cases, but about five times slower and with no probabilities to lean on.
- **Jev's top choice, no threshold**: missed suspected abuse in the first comparison.
- **A third-party Jev endpoint (jev-ai.pro)**: not run by TypeSafe and with no named operator; every message and the balance would sit with an unknown party.

## Consequences

- Every emergency now depends on a model call. Jev answers in well under a second, and when it does not, the fallback answers.
- When Jev hangs, the user can wait up to about 13 seconds (3 + 10) before a reply. This happened on a few percent of calls in the comparison.
- The first call after the backend starts opens a new connection and can take a few seconds; if it times out, the fallback answers.
- Product rule 4 still holds when both classifiers fail: the user always gets the emergency contacts.
- A third outside service, TypeSafe, joins DeepSeek and LangSmith. Messages are synthetic (rule 5), so sending them there is acceptable.
- Two classifiers behave differently: Jev's decision uses probabilities, DeepSeek's uses its label alone. Both passed the safety cases, and unit tests cover all three paths (Jev answers, DeepSeek answers, both fail).
- Jev is new and early access, and its SDK has had breaking changes, so the SDK version is pinned.
