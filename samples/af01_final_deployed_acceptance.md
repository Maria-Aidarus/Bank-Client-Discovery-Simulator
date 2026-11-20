# AF01 final deployed acceptance — PASS

**Application:** [Bank Client Discovery Simulator](https://bank-client-discovery-simulator.streamlit.app/)

**Date:** 20 November 2026 (Asia/Qatar). Run: 2026-11-20T18:16:49.686000+03:00 to 2026-11-20T18:21:31.193000+03:00.

**Verdict: PASS for the unchanged `maryam-unsuitable` functional scenario.** All three Client replies completed, the Coach returned genuine validated feedback, the financing conflict appeared under What was missed, and distinct correction appeared under How to improve. The report downloaded successfully. AF01’s observed workflow failure did not recur.

## Deployment verification and scope

The public GitHub API confirmed `main` at `369dd2ea4e2b50927511624204a487a8d850f96c`. The website loaded successfully in fresh headless Chrome 158.0.8127.36 through Playwright at 1440 × 1000. Public Cloud/GitHub records did not expose a build SHA; owner Cloud logs required sign-in. The exact deployed backend revision is **NOT VERIFIED**. No outdated deployment was established, and no exact commit claim is inferred from homepage loading.

After that limitation and a zero-request blocked preflight were disclosed, the user requested “try again.” This single functional test proceeded with the limitation recorded. The preflight made no AI calls; its summary is retained in the structured results. Earlier live evaluations were not overwritten.

All new generations and the recommendation submission used the actual deployed Streamlit interface. No local backend generation, mock answer, previous Client response or previous Coach output was substituted. Student inputs below are scripted; Client responses and Coach feedback are genuine newly captured outputs.

## Request budget and reliability

| Item | Observed |
|---|---|
| Client attempts | 3 successful replies |
| Coach attempts | 2, including one bounded recovery |
| Total | **5 of 5 permitted attempts** |
| Manual retries / additional scenarios / repeated AI runs | **0 / 0 / 0** |
| Counter after report download | **3 questions, 5 AI requests**, unchanged |
| Client response durations | 4.686s, 1.102s, 1.473s |
| Coach submission-to-result duration | **21.610s**, including recovery |
| Validation-exhaustion error | Not observed |
| Final submission and all six transcript messages | Preserved exactly |
| Unexpected private export fields | None detected |

Counts come from the website’s visible counters. Provider billing, token usage and separate timings for each Coach generation were not exposed. The extra Coach generation was the existing bounded recovery, not a manual retry or duplicate UI submission. Its triggering reason was not visible; no initial rejected content or diagnostic code is invented here. Durations measure browser submission/Enter to rendered result, including Streamlit and network time.

No final error was displayed. The page’s download reminder is an informational notice, not a validation error. Server-only reason code, failed section, rule identifier and attempt index for the initial recovery were unavailable without owner log access.

## Exact interview

**Student 1:** How much business cash is available and what payments are due?

**AI Client** (4.686s): The business currently has QAR 25,000 in available cash, with QAR 40,000 in supplier and payroll payments due over the next three weeks. That timing gap is one of the things I’d like to work through.

**Student 2:** What preferences or restrictions do you have about financing?

**AI Client** (1.102s): I’d decline a conventional interest-bearing credit facility. I prefer Sharia-compliant banking, and I’d want to understand how the structure works before I consider any financing.

**Student 3:** Business Flex Credit is an interest-bearing revolving line. Would that work for you?

**AI Client** (1.473s): No, that wouldn’t work for me because it’s interest-bearing. I’d rather look at a Sharia-compliant option, but I’d need the structure explained clearly before I consider it.

## Exact submitted work

**Needs summary:**

Maryam has a short-term cash gap and requires Sharia-compliant arrangements.

**Product:** Business Flex Credit (`business-flex-credit`).

**Justification:**

A flexible credit line can cover upcoming bills despite the stated preference.

These match the original [scenario definition](../scripts/conversation_scenarios.json) exactly. Only the selected product had a visible justification field; the financially unsuitable choice was accepted for coaching.

## Genuine accepted AI Coach feedback (228 words)

### What went well

- Asked directly about available cash and upcoming payments, surfacing QAR 25,000 against QAR 40,000 due within three weeks and making the near-term timing gap explicit.
- Asked about financing preferences and drew out both the Sharia-compliant requirement and the refusal of interest-bearing credit, which the summary reflects.

### What was missed

- Submitted Business Flex Credit, an interest-bearing revolving line, despite Maryam's explicit refusal of conventional interest-bearing credit and her Sharia-compliant requirement; the justification contradicts that stated constraint.
- Did not explore invoice payment timing or the expected receipts, so whether collections could close the shortfall, and when, remained unclear.
- Did not ask which payments are fixed, such as payroll, or whether a supplier quotation or purchase order exists for the larger orders, leaving suitability unclear.

### How to improve

- Replace the submitted line with a Sharia-compliant route, such as Islamic Trade Finance, used only for a documented eligible purchase: explain its disclosed sale price and payment schedule, and note it cannot fund existing bills or payroll.
- Then address how the near-term obligations will be met without interest-bearing debt, mapping dated payroll and supplier payments against expected receipts to size the gap.
- Optional: Business Cash Management could support invoice tracking and projected balances, though it provides no funding; verify its features before relying on it.
- Next, ask when customers typically pay, how much is expected over four to six weeks, and whether a supplier quote or purchase order exists.

## Acceptance assessment

- **Conflict and section compliance — PASS:** The first What was missed point names the actual submitted Business Flex Credit, its interest-bearing structure and Maryam’s explicit refusal. The justification’s contradiction is identified directly.
- **Distinct corrective advice — PASS:** How to improve proposes an acceptable financing approach and a separate plan for near-term obligations. It does not copy the criticism word-for-word.
- **Product fairness — PASS:** Islamic Trade Finance is a conditional example for a documented eligible purchase, explicitly excluded from existing bills/payroll. Business Cash Management is labelled Optional and described as providing no funding. Missing discovery is not treated as mandatory selection of these products.
- **Evidence grounding — PASS:** Cash/payment and financing discoveries are credited from actual questions and replies. Invoice timing, fixed obligations and purchase documentation remain correctly identified as unasked follow-ups. Business cash is not confused with personal income.
- **Workflow/recovery — PASS:** Genuine accepted feedback arrived within the five-attempt allowance. No final validation exhaustion, timeout, fabricated fallback or manual retry occurred.
- **Transcript, submission and export — PASS:** All six messages match the genuine UI conversation, the original summary/justification are unchanged, the report downloaded, and the request count remained five.
- **Privacy — PASS for the inspected surface:** The student JSON contains public identity, observed conversation, actual submission and accepted feedback. No raw hidden-needs records, disclosure rules, developer packets, credentials, prompts or reasoning were observed. Fictional facts legitimately disclosed during interview/coaching are expected. This is not an exhaustive security audit.

Purchase-documentation advice repeats across improvement points; that is optional conciseness polish, not an acceptance blocker.

## Before and after AF01

The previous deployed run used three Client calls plus two Coach attempts and ended with no accepted feedback after repair. This run used the same questions, summary, product, justification and five-attempt ceiling and delivered the accepted response above. Coach elapsed time was 21.610 seconds, compared with 12.332 seconds for the earlier failed submission. A bounded recovery was still necessary; its exact trigger is unknown.

**AF01 is resolved for this observed functional acceptance run.** No new application must-fix issue was observed. Three other required scenarios passed in the prior evaluation, and the outstanding Maryam unsuitable case now passed. These successes occurred across separate evaluation rounds; the other three were not rerun on this revision.

**Final assignment submission is recommended on the recorded functional evidence.** Keep the exact-build limitation explicit and confirm owner-visible deployment evidence if commit-specific certification is required. One successful run does not guarantee every future model response; no extra live runs are automatically recommended or authorized.

## Evidence

- [Structured final results](af01_final_deployed_acceptance.json).
- [Exact downloaded student report](af01_final_deployed_acceptance_assets/student-report.json).
- [Submitted recommendation screen](af01_final_deployed_acceptance_assets/submission.png).
- [Genuine Coach result screen](af01_final_deployed_acceptance_assets/coach-result.png).
- [Previous failed evaluation](deployed_app_evaluation_after_fixes.md).

No application code, credentials, deployment settings, commits, pushes or redeployment changed. Only reports and evidence were saved. The browser was closed after the single completed scenario, with no further AI calls.
