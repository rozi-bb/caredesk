# ADR-0033: Cost per user is computed by a report script from usage records

- Status: Accepted
- Date: 2026-10-16

## Context

Roadmap step 25 asks for cost per user. Every chat request already writes one `usage_events` row with the account, input and output tokens, time, route, and channel (prd.md F10). Every trace in LangSmith carries `account_id`, `user_id`, and `role` as metadata. Nothing yet turns tokens into money.

Prices checked on 2026-10-16:

- DeepSeek `deepseek-flash`, per million tokens ([pricing page](https://api-docs.deepseek.com/quick_start/pricing)): input $0.15 off-peak and $0.30 peak (cache miss), $0.003 and $0.006 (cache hit); output $0.60 off-peak and $1.20 peak. Peak hours are 01:00–04:00 and 06:00–10:00 UTC, Monday to Friday.
- Jev, per million tokens ([typesafe.ai](https://typesafe.ai)): input $0.042, output free. Two triage calls measured on 2026-10-16 used 586 input tokens each.

## Decision

`scripts/cost_report.py` prints cost per account, per role, and per channel, computed when the report runs:

- DeepSeek cost per request from its `usage_events` tokens, at the peak or off-peak price for the hour the request was made.
- Every input token is priced as a cache miss, because `usage_events` does not record cache hits. The DeepSeek figure is therefore an upper bound.
- Jev is not in `usage_events`, because it is not a LangChain model. Its cost is estimated as 586 input tokens per request.
- Prices live in one table in `src/backend/costs.py`, with the date they were checked.

A LangSmith dashboard grouped by `account_id` shows cost from traces, as a second view to compare against.

## Alternatives considered

- **Store the cost in each `usage_events` row when the request ends**: the price at that moment is kept, but it needs a migration, and the cache-hit and Jev gaps remain.
- **Record cache hits and Jev tokens too**: closer figures, but it changes the chat endpoint, the triage node, and the table. Left for a follow-up once the size of the gap was known (see Consequences).
- **A cost page in Chainlit**: only the home's owner needs the numbers, and the app is not deployed (ADR-0026).
- **LangSmith only**: its price table may not know DeepSeek's peak and off-peak prices or Jev at all, and its numbers cannot be checked against our own records.

## Consequences

- Prices are not tracked over time. If DeepSeek or TypeSafe change their prices, the table is updated and older requests are recomputed at the new price.
- Chinese public holidays, which DeepSeek bills off-peak, are counted as normal days, so cost on those days is slightly overstated.
- The LangSmith dashboard and the report disagree by a lot. On 2026-10-16 the 41 recorded requests cost $0.0399 in the report and $0.0084 in LangSmith. LangSmith prices `deepseek-flash` at the off-peak rate and counts cache hits, and 84% of the input tokens on the backend's model calls were cache hits (the system prompt and tool descriptions repeat on every call). The report is a safe upper bound, not the expected bill; recording cache hits in `usage_events` would close most of the gap.
