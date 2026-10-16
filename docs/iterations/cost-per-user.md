# Cost per user

| | |
|---|---|
| Scope | Roadmap step 25, prd.md F10, [ADR-0033](../adr/0033-cost-per-user-report.md) |
| Date | 2026-10-16 |
| Result | Done; the report is an upper bound |

## Why

Every chat request already wrote its tokens to `usage_events`, and every trace carried `account_id`, `role`, and `channel`. Nothing turned tokens into money.

## Build

| Step | What |
|---|---|
| Prices | DeepSeek pricing page: `deepseek-flash` has peak and off-peak prices and a cache-hit price. TypeSafe site: Jev input $0.042 per million, output free. One triage call measured at 586 input tokens |
| `src/backend/costs.py` | Price table with the date it was checked; `is_peak()`, `deepseek_cost()`, `build_report()`, `load_usage()` |
| `scripts/cost_report.py` | Read-only report per account, role, and channel, with the assumptions printed under it |
| `scripts/create_cost_dashboard.py` | Creates the "CareDesk cost" dashboard in LangSmith: three numbers at the top (total cost, requests, average cost per request, backend requests only), then cost and requests per account and cost per role and per channel, from root traces. `--replace` rebuilds it. The API only accepts the newer (V2) chart definitions; a failed run deletes its half-built dashboard |

## Test

| Check | How | Result |
|---|---|---|
| Peak hours | Weekday 01:00–04:00 and 06:00–10:00 UTC are peak, edges included at the start only; weekends off-peak; a Jakarta time is judged in UTC | Pass |
| Arithmetic | One million input and output tokens cost $0.75 off-peak and $1.50 peak; report lines add up per account, role, channel, and in total | Pass |
| Query | A usage row inserted in a seeded test database comes back with its account's email and role | Pass |
| Real data | 41 requests from 2026-10-13 to 2026-10-16: $0.0399 in total, about $0.001 per request; Jev $0.0010 of it | Pass |
| Dashboard | Four charts created in LangSmith and checked by the owner in the UI: per account, requests, role, and channel all show data. The API returns no chart data, so this was checked by eye | Pass |
| Dashboard totals | The filter behind the three numbers, run through the SDK, matches 41 root traces costing $0.0084, the same requests as `usage_events` | Pass |

## Findings

- LangSmith prices the same 41 requests at $0.0084, almost five times less. 84% of the input tokens on the backend's model calls were cache hits, which DeepSeek bills at 2% of the normal input price, and LangSmith uses the off-peak price. The report's assumption that every input token is a cache miss is safe but far from the real bill.
- Recording cache hits per request (`input_token_details.cache_read` from the usage callback, one new column) would close most of the gap. Not done here; it changes the chat endpoint and the table.
- 355 root traces in the `caredesk` project have no account: they come from Studio, not the backend. Studio runs do carry `role` (including `unknown` when no context is set), so the cost-per-role chart also counts Studio runs, while the account and channel charts count only backend requests.
- The 18 requests from 2026-10-13 were traced before the backend added `channel` to the metadata, so the cost-per-channel chart has no bar for that day. `usage_events` counts them as `web`, the column's default. The totals at the top therefore select backend requests by `account_id`, not `channel`.
