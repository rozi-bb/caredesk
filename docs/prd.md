# CareDesk — Product Requirements

| | |
|---|---|
| Status | Draft |
| Release | 1 |
| Last updated | 2026-10-01 |

## 1. Problem

Staff and families at a nursing home ask the same administrative questions every day: today's schedule, upcoming activities, visiting rules, what a resident is entitled to, where to file a complaint. Answers are scattered across schedules, the home's handbook, and federal regulations. Staff spend time repeating answers, and families wait for them.

## 2. Product

**CareDesk** is an administrative assistant for one fictional nursing home, *Evergreen Care Home*. It answers questions from the home's operational data and from its rules, in English.

Guiding principle: every answer can be traced to a source, and the assistant stops exactly at the medical line.

## 3. Users and permissions

| Role | Release | Can see | Cannot see |
|---|---|---|---|
| **Staff** | 1 | All residents' schedules, activities, visits, and incident records | Nothing restricted in release 1 |
| **Family member** | 1 | Schedules, activities, and visits of their own linked resident. Billing only if their link grants financial access | Any other resident. Billing without financial access |
| **Resident** | 2 | Their own schedule, activities, and visits | Any other resident |

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
| Rules | 12–15 F-tags covering resident rights, visiting and family notification, complaints, and restraint and abuse protection | CMS State Operations Manual, Appendix PP (public domain) |
| Handbook | Evergreen's own policies, written to be consistent with the F-tags above | Written for this project |
| Operational | Residents, family links, staff, schedules, activities, visits, incidents, billing | Synthetic, generated with a fixed seed |

The F-tags are chosen from real questions in section 4, not the other way around. Clinical regulations and building or fire-safety regulations are deliberately excluded.

The synthetic data deliberately includes hard cases: residents with near-identical names, and families where members have different access levels.

## 8. Success criteria

Release 1 is done when evaluation shows:

| Category | Question | Target |
|---|---|---|
| Correctness | Does the answer match the data? | Set after the first baseline run |
| Groundedness | Is every rule-based answer supported by the cited source? | Set after the first baseline run |
| Safety | Are clinical questions declined and emergencies handled? | 100% |
| Access control | Do attempts to reach another resident's data fail? | 100% |

Safety and access control are pass/fail: a single failure blocks the release.

## 9. Out of scope for release 1

- Resident access (release 2)
- Write actions such as booking a visit, and human confirmation for them
- Data entry forms
- End-user UI, backend API, and real login
- Notifications outside the app (email, messaging)
- Usage limits and payments. The home pays per use; there is never a hard limit, because a limit could block an emergency message.
- More than one nursing home

## 10. Open questions

- Should family members see medication schedules, or only that care is scheduled?
- Which emergency contacts and instructions does the assistant show?
- Exact F-tag list, to be chosen from the example questions during data preparation.
