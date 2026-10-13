# ADR-0019: Release 2 is a thin app that runs locally

- Status: Accepted
- Date: 2026-10-13

## Context

Release 1 shipped a trustworthy agent that only runs in LangGraph Studio, with identity typed in by hand. The playbook's stage 2 is a thin version that runs end to end. Its steps 10–26 cover backend, database, login, chat endpoint, UI, tests, deployment, and monitoring. Deployment needs a paid server and domain, which the project owner does not want yet.

## Decision

Release 2 wraps the release 1 agent into an app, with no new assistant features. Work is split into three packages, each ending in something that can be tried:

| Package | Playbook steps | Ends with |
|---|---|---|
| A. Backend | 10–13, with the backend parts of tests 18–19 | Sign in and chat through the API, identity from the account |
| B. UI | 16, with the UI parts of test 19 | The full app in a browser on the local machine |
| C. Deploy and monitor | 20–26 | The app on the internet |

Release 2 is packages A and B, running locally. Package C comes later. The four evaluations run again in every package to catch regressions.

## Alternatives considered

- **Include deployment now**: costs money before anyone needs the app online.
- **Add resident access or write actions at the same time**: two kinds of change in one release make failures harder to trace.
- **Two packages (A and B together)**: package A would end with nothing visible to try for a long time.

## Consequences

- Release 2 is not reachable by anyone else; it is shown by running it locally.
- Choices in A and B must not block package C, for example by depending on paid hosting (ADR-0020).
- Residents and write actions stay in the roadmap's Later list.
