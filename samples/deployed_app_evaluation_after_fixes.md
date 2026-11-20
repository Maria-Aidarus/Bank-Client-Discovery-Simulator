# Post-fix deployed application acceptance evaluation

**Application:** [Bank Client Discovery Simulator](https://bank-client-discovery-simulator.streamlit.app/)

**Test date:** 20 November 2026, 16:14–16:26 (Asia/Qatar, UTC+03:00)

**Overall: PARTIAL PASS — not ready for unconditional final submission.** All four scenarios were attempted in fresh sessions. Three completed; Maryam unsuitable could not obtain validated Coach feedback. No timeout recurred.

## Revision evidence and environment

Target revision: `e957f01c03b33ba3195b6cff619d0845ada4f1ac`. Public GitHub deployment and Actions queries returned no records, and the commit-status query contained zero statuses. The aggregate pending status is not a Cloud build result. Owner-visible Cloud build logs were unavailable. **The exact deployed SHA is NOT VERIFIED.** This limitation was reported before any AI calls; testing proceeded under the operator’s confirmation that the update was deployed.

Evidence beyond homepage loading: the deployed stylesheet hash exactly matches the local post-fix stylesheet (`d7a7fcea142aed4719fbd86799ade430e0713647789cc4152ffb8a408d6a6b69`); the new mobile inset is active; and the Maryam failure message matches the updated Coach repair-exhaustion path. These verify relevant updated behavior, not the exact full deployment revision.

Playwright controlled headless Chrome 158.0.8127.36 on macOS. Every scenario used a fresh isolated browser context at 1440 × 1000, with empty transcript and zero request counter. Mobile spacing was separately checked in a fresh 390 × 844 touch-enabled context. All questions and submissions went through the deployed website. No local backend generation, fake output or prior AI response was substituted.

The exact questions, summary, products and justifications came from [the original scenario definitions](../scripts/conversation_scenarios.json). Student inputs are scripted; all Client replies and displayed Coach feedback below are genuine new website outputs. Rejected Coach content was not exposed and is not invented here.

## Scenario outcomes and requests

| Scenario | Verdict | Client attempts | Coach attempts | Outcome |
|---|---|---:|---:|---|
| maryam-strong | PASS | 7 | 1 | Fair Cash Management feedback; unresolved cash gap still identified. |
| maryam-unsuitable | FAIL | 3 | 2 | Coach grounding/section validation exhausted after one repair. |
| mohamed-strong | PASS | 6 | 1 | Contextual follow-up answered; two products submitted; genuine feedback. |
| mohamed-unsuitable | PASS | 3 | 1 | Liquidity conflict in What was missed; distinct corrective advice. |

**24 of 30 permitted AI attempts**, based on the visible per-session counters (8 + 5 + 7 + 4). All 19 Client attempts succeeded. Four Coach submissions consumed five attempts; three returned accepted feedback, and one failed after its built-in repair. No manual retries, scenario replay or extra AI calls occurred. The failed content-validation submission was not treated as provider unavailability; the remaining fresh scenarios continued successfully.

Provider-side request traces, token usage, billed cost and returned model identifier were not exposed in the student UI. The project/operator configuration states Ollama Cloud and `deepseek-v4.1-flash`; no independent model-identity claim is made.

## Before and after

| Check | Original evaluation | This evaluation | Assessment |
|---|---|---|---|
| Unselected trade finance in Maryam strong | Treated as a missed required explanation. | No such omission; genuine contingency critique retained. | Resolved in this run. |
| Mohamed contextual access question | Timed out after 60.648 seconds. | Answered in 1.245 seconds; complete two-product workflow. | Did not recur; underlying original cause remains unknown. |
| Maryam unsuitable feedback sections | Warning appeared only in How to improve. | No accepted feedback after repair. | Unresolved; new workflow-completion failure. |
| Mohamed unsuitable feedback sections | Not tested in original round. | Conflict first in What was missed; correction in How to improve. | Verified in this run. |
| Mobile badge overlap | Lower selection controls overlapped badges. | Both scrolled buttons above the reserved bottom strip. | Resolved at 390 × 844. |

The 60-second timeout was not changed. A successful new access response is evidence of this run, not proof of a permanent timeout fix. Maryam strong feedback decreased from 273 to 236 words. New Mohamed strong and unsuitable feedback were 226 and 241 words. The previous Maryam unsuitable response was 223 words; this run has no accepted output to compare. All three successful new responses are within the 180–260-word soft target.

## Must-fix issue

### HIGH — AF01: Maryam unsuitable cannot complete Coach generation

**Observed:** After the exact three questions and unchanged unsuitable Business Flex Credit submission, the website displayed:

> The AI Coach still returned unfair product critique or misplaced suitability feedback after one repair.

The counter showed **3/30 questions and 5/40 requests**. The Coach stage took **12.332 seconds**, including two generation attempts. No validated feedback was shown; the report contains `coach_feedback: null`. The Retry coaching option was visible, but it was not clicked. The transcript, exact needs summary and product justification remained intact and downloadable.

**Expected:** A genuine validated response identifying the interest/Sharia conflict under What was missed and a different practical correction under How to improve, within the existing bounded repair allowance.

**Reproduce:** Start a fresh Maryam interview; use the three `maryam-unsuitable` questions, finish the interview, and submit its unchanged summary, Business Flex Credit and justification. Inspect the Coach result. This is the sequence that failed once; repeated reproducibility has not been established.

**Known versus uncertain:** Repair/grounding exhaustion is confirmed. The public interface does not expose either rejected Coach response or distinguish `unselected_product_critique` from `suitability_sections`. It cannot establish whether the model ignored the instructions, the validator rejected equivalent valid wording, or another grounding condition failed. There was no timeout/authentication/provider-availability error for this submission.

**Investigate:** `src/bank_simulator/agents/coaching_validation.py` and `src/bank_simulator/agents/coach_agent.py`. Use safe failed-check/section diagnostics to identify the actual rejection reason. Retain schema validation, the bounded repair policy, exact student answers and explicit retry. Do not fabricate feedback, disable the guard indiscriminately or add paid retries without evidence.

**Before submission:** Correct the verified cause and authorize a limited new run of the same Maryam unsuitable scenario. This round does not verify that its unsuitable financing conflict reaches the correct section, because no accepted feedback was delivered.

[Failure screenshot](deployed_app_evaluation_after_fixes_assets/maryam-unsuitable-feedback.png).

## UI, privacy and reliability checks

- All five displayed product accordions matched the editable catalogue, including limitations and eligibility. No new page-level JavaScript exception was captured.
- Each scenario started with a separate isolated browser context, no transcript and zero requests. All four downloaded reports have distinct session IDs and the correct public client identity.
- Every Client turn preserved the transcript prefix and appended one student message plus one response. All 19 Client replies succeeded; no duplicate question or Client response was observed.
- Only selected products had visible justifications. Inline missing-summary, missing-product and missing-justification errors were checked without AI calls. Both Mohamed strong products and their separate exact justifications survived submission and export.
- All four reports downloaded. Exact submitted summaries and recommendations matched the predefined inputs, including the financially unsuitable choices. Downloads and review-expander interaction did not increase the request count.
- All four reports used only public client identity, observed messages, actual submitted work and accepted feedback (or null). No hidden-needs record, disclosure metadata, credential field, system prompt, developer packet or raw reasoning was observed. No credentials were requested or extracted. This is not an exhaustive security audit.
- The failed Coach submission preserved data, displayed a safe error and exposed an explicit retry. Invalid feedback was not silently converted into a successful result. Retry execution was not tested.
- At 390 × 844, the selection app viewport ends at y=788, reserving 56 pixels. Maryam’s scrolled button ends at y=787.688; Mohamed’s ends at y=674.844, both clear of the hosting badges. No horizontal overflow was measured. Physical devices and other engines were not tested.
- No additional frontend regression was observed. The failed Coach validation is a backend completion regression, safely rendered by the UI. Concurrent double-click/reconnection races were not exercised.
- Nonblocking Cloud-shell event/user-detail and Heap analytics errors were captured. These did not prevent the successful workflows; no evidence connects them to the Coach grounding failure.

## Request duration evidence

Client Enter-to-response durations ranged from **1.223 to 2.480 seconds**, mean 1.591. Coach submission-to-result durations were 7.249 seconds (Maryam strong), 12.332 seconds (Maryam unsuitable failure), 13.876 seconds (Mohamed strong), and 12.345 seconds (Mohamed unsuitable). These are browser-observed end-to-end times, not isolated inference or per-HTTP-attempt measurements. Individual turns and timestamps are recorded in the structured results.

## Genuine conversations, submissions and feedback

### maryam-strong — PASS

**AI Client assessment:** Responses stayed in character, used the correct business cash and payment figures, disclosed Sharia preference after a financing question, and reacted to Cash Management without selecting a complete banking solution for the student.

**AI Coach assessment:** Credited the no-funding limitation and the discovered cash facts. Identified the genuinely unresolved cash-gap contingency and actual unanswered customer questions. No unselected trade-finance explanation was treated as a missed requirement. Conditional purchase-finance advice remained in How to improve.

**Student 1:** How do late customer payments affect your business?

**AI Client** (2.480s): When customers pay late, it can leave us short of cash for payroll and for paying supplier invoices on time. That timing squeeze is the main thing I want to manage better as we take on larger retail orders.

**Student 2:** How much cash is available, and what payments are due?

**AI Client** (1.223s): We have QAR 25,000 in available cash. Over the next three weeks, we have QAR 40,000 in supplier and payroll payments due, so the timing is tight.

**Student 3:** What payments are you expecting from customers, and when?

**AI Client** (1.333s): We're expecting about QAR 60,000 from outstanding customer invoices over the next four to six weeks, though I don't have firm receipt dates. That uncertainty is what makes the next few weeks a bit awkward to plan around.

**Student 4:** Which obligations cannot be postponed?

**AI Client** (1.421s): Payroll has fixed dates and can’t be postponed. The supplier payments are also due over the next three weeks, but I’d want to check the exact terms on those before treating any of them as fixed.

**Student 5:** What financing arrangements would you accept?

**AI Client** (1.505s): I wouldn’t take a conventional interest-bearing credit facility. I’m open to looking at Sharia-compliant financing, but I’d need the structure explained clearly before I’d consider it—especially for short-term working capital around these payment dates.

**Student 6:** Do you have supplier quotations or purchase orders for the larger orders?

**AI Client** (1.456s): No, I don’t have a supplier quotation or a purchase order for the larger orders yet. So any immediate solution would need to fit around our scheduled payments and the uncertain timing of customer receipts.

**Student 7:** Business Cash Management can track invoices and upcoming payments but supplies no funding. Would that help?

**AI Client** (2.319s): It could help with the visibility and invoice follow-up I need, but I understand it won’t fund the gap between the QAR 40,000 due and the uncertain customer receipts. Would it let me see a projected balance after payroll and supplier payments while keeping control over when I schedule supplier payments?

**Actual submitted needs summary:**

The business faces a possible QAR 15,000 timing gap. Follow up collections and fixed obligations, preserve the Sharia requirement, and establish a contingency for delayed receipts. Purchase finance needs qualifying documentation.

**Actual submitted products and justifications:**

- **Business Cash Management** (`business-cash-management`): Useful for collections and payment visibility. It does not fund the gap, so a separate contingency is required.

**Genuine AI Coach feedback** (236 whitespace-delimited words):

**What went well**

- Systematically uncovered the core timing issue: late retailer payments, QAR 25,000 cash against QAR 40,000 due in three weeks, and QAR 60,000 expected with uncertain receipt dates.
- Confirmed payroll cannot be postponed and that there is no supplier quotation or purchase order for the larger orders.
- Captured the Sharia preference and correctly framed Business Cash Management as visibility and collections support that does not fund the gap; the summary preserves this limitation and flags a separate contingency.

**What was missed**

- The immediate QAR 15,000 shortfall still lacks a concrete plan; stating that a separate contingency is required does not establish what Maryam will do if receipts arrive late.
- The client's closing question, whether cash management can show a projected balance after payroll and supplier payments while preserving control over supplier scheduling, was not answered, leaving a practical product-fit point unresolved.
- Although Maryam offered to check exact supplier terms, the student did not follow up on which supplier payments might be flexible, missing a potential cash-timing lever.

**How to improve**

- Answer the closing question directly by confirming the relevant cash-management features from the catalogue, subject to eligibility and accurate invoice/payment data, then verify Maryam's account setup.
- Set out an explicit shortfall plan: protect fixed payroll, chase overdue invoices, confirm supplier timing, and set a review trigger for expected receipts.
- Keep any Sharia-compliant financing discussion tied to a documented eligible purchase, not payroll or existing bills, and verify any transaction-review requirements before suggesting it.

[Recommendation screen](deployed_app_evaluation_after_fixes_assets/maryam-strong-recommendations.png) · [Coach result screen](deployed_app_evaluation_after_fixes_assets/maryam-strong-feedback.png).

### maryam-unsuitable — FAIL

**AI Client assessment:** All three questions received coherent responses. Maryam explicitly refused conventional interest-bearing credit, including the proposed Business Flex Credit.

**AI Coach assessment:** No validated Coach feedback was returned. The website rejected feedback after its single built-in repair and displayed a safe grounding/section error. The actual rejected output and the failed check category were not exposed; neither model noncompliance nor a validator false positive can be established from the browser.

**Student 1:** How much business cash is available and what payments are due?

**AI Client** (1.708s): Right now the business has about QAR 25,000 in available cash, and I have QAR 40,000 in supplier and payroll payments due over the next three weeks. That timing is a concern, so I'd like to review how to manage the shortfall without disrupting day-to-day operations.

**Student 2:** What preferences or restrictions do you have about financing?

**AI Client** (1.357s): I’d prefer Sharia-compliant financing, and I wouldn’t take a conventional interest-bearing credit facility. Before considering anything, I’d want the structure explained clearly so I understand how it works and what it would mean for the business.

**Student 3:** Business Flex Credit is an interest-bearing revolving line. Would that work for you?

**AI Client** (1.664s): That wouldn’t work for me, since it’s an interest-bearing revolving line and I’d prefer Sharia-compliant financing. I’d rather review a Sharia-compliant option, with the structure and requirements explained clearly before I consider it.

**Actual submitted needs summary:**

Maryam has a short-term cash gap and requires Sharia-compliant arrangements.

**Actual submitted products and justifications:**

- **Business Flex Credit** (`business-flex-credit`): A flexible credit line can cover upcoming bills despite the stated preference.

**Coach feedback:** None accepted or shown. The website returned the AF01 error after one built-in repair. Neither rejected raw response was exposed; no coaching text is fabricated or substituted.

[Recommendation screen](deployed_app_evaluation_after_fixes_assets/maryam-unsuitable-recommendations.png) · [Coach result screen](deployed_app_evaluation_after_fixes_assets/maryam-unsuitable-feedback.png).

### mohamed-strong — PASS

**AI Client assessment:** The formerly timed-out contextual access question received a genuine same-day-access response in 1.245 seconds. Responses kept the QAR 1,200 emergency balance separate from the future QAR 9,000 goal over 18 months; QAR 500 remained a conditional contribution needing an expense review.

**AI Coach assessment:** The genuine feedback credited discovery, evaluated the two actual accounts fairly, and identified unresolved affordability and reserve-building questions. It preserved may-forfeit wording and required verification of undocumented bonus effects of changing transfers.

**Student 1:** What are you saving for, and what amount and deadline do you have in mind?

**AI Client** (1.348s): I’m aiming to set aside QAR 9,000 over 18 months for a professional certification course and exam fees. I’d like to keep that separate from my emergency fund so the two goals don’t get mixed together.

**Student 2:** What income comes in, and what fixed bills go out each month?

**AI Client** (1.242s): I take home QAR 8,000 a month, and my fixed monthly bills come to about QAR 4,600. That’s before groceries and other irregular expenses.

**Student 3:** How much emergency money is set aside, and which irregular expenses come up?

**AI Client** (1.404s): I have QAR 1,200 set aside for emergencies. The irregular costs that tend to come up are car maintenance and family travel; either can reduce or wipe out what I manage to save in a month, and an unexpected repair could use most of that emergency money.

**Student 4:** How quickly would you need access to that money?

**AI Client** (1.245s): I’d need my emergency money to be available the same day if something comes up. For the certification savings, I’d like it kept separate so I can see the progress clearly.

**Student 5:** How much could you comfortably save each month, and could you adjust contributions?

**AI Client** (1.975s): I’m not certain yet what monthly amount would be comfortable once groceries, car maintenance, and family travel are accounted for. An average of QAR 500 a month might work for the certification goal, but I’d want to check that against those irregular expenses and keeping my emergency savings intact—and I’d need to be able to adjust or pause the contributions when a higher-expense month comes up.

**Student 6:** Goal Saver Account has withdrawal delays. Everyday Access Account has an instant-access reserve. How would that affect your plans?

**AI Client** (2.147s): That makes sense: my emergency reserve would need the instant-access space, since I can’t wait several business days for a repair. For the certification goal, a separate account showing progress appeals to me, but I’d want to confirm how adjusting or pausing contributions affects the goal bonus, and whether any early withdrawal from that goal account would forfeit it.

**Actual submitted needs summary:**

Keep emergency funds accessible, account for irregular expenses, and assess a flexible contribution toward certification separately.

**Actual submitted products and justifications:**

- **Everyday Access Account** (`everyday-access-account`): An accessible reserve for unexpected expenses.
- **Goal Saver Account** (`goal-saver-account`): For the dated certification goal, with adjustable contributions and a separate emergency reserve.

**Genuine AI Coach feedback** (226 whitespace-delimited words):

**What went well**

- Opened with a clear goal question and established the QAR 9,000 certification target over 18 months, kept separate from emergency savings.
- Covered income (QAR 8,000), fixed bills (about QAR 4,600), the QAR 1,200 emergency balance and irregular car/travel costs.
- Explored same-day emergency access and contribution flexibility, then mapped the Everyday Access reserve versus the Goal Saver for the dated goal.

**What was missed**

- QAR 500 a month remains conditional: the client said he was not certain it was comfortable after groceries and irregular expenses, and no monthly surplus or budget buffer was quantified.
- No emergency-reserve build target or split of surplus between rebuilding the reserve and the certification goal was discussed.
- The client asked how pausing/adjusting contributions and early withdrawal affect the Goal Saver bonus; the transcript does not resolve this. The catalogue states early withdrawal may forfeit a bonus but does not detail how pausing/adjusting contributions interacts with it, so it needs verification.

**How to improve**

- Convert the target into a reviewable plan: after QAR 4,600 bills and realistic groceries/irregular costs, agree a contribution the client is comfortable starting with, then review after a high-expense month.
- Ask what emergency reserve target he wants and how much of any monthly surplus should go there before the certification transfer.
- Before relying on the Goal Saver, confirm with the bank how pausing/adjusting transfers and early withdrawal affect any goal bonus, and record the answer.

[Recommendation screen](deployed_app_evaluation_after_fixes_assets/mohamed-strong-recommendations.png) · [Coach result screen](deployed_app_evaluation_after_fixes_assets/mohamed-strong-feedback.png).

### mohamed-unsuitable — PASS

**AI Client assessment:** The Client stated same-day access was necessary and explicitly rejected several-day withdrawals for emergency money, while allowing a separate planned-goal use.

**AI Coach assessment:** What was missed explicitly put the unsuitable emergency-money recommendation first. How to improve gave a distinct correction and labelled Everyday Access as an optional alternative. The Coach correctly treated the certification details and affordability as undiscovered rather than inventing student questions.

**Student 1:** How much emergency money do you have set aside?

**AI Client** (1.463s): I have about QAR 1,200 set aside for emergencies right now. I’m aware that an unexpected repair could use up most of that, so I’d like to build it up more steadily.

**Student 2:** How quickly would you need access if an unexpected bill arrived?

**AI Client** (1.255s): I’d need it available the same day, since an unexpected bill or repair could be urgent. That’s why easy access matters to me for emergency money.

**Student 3:** Goal Saver Account withdrawals take several business days. Would that work for your emergency money?

**AI Client** (1.688s): No, that wouldn’t work for my emergency money—I’d need same-day access in case of an urgent bill or repair. I could consider that account for a separate planned savings goal, but I’d want my emergency reserve kept somewhere I can reach immediately.

**Actual submitted needs summary:**

Mohamed needs same-day access to his emergency reserve.

**Actual submitted products and justifications:**

- **Goal Saver Account** (`goal-saver-account`): Put all emergency money here to encourage saving despite the withdrawal delay.

**Genuine AI Coach feedback** (241 whitespace-delimited words):

**What went well**

- You asked about emergency savings and surfaced the QAR 1,200 reserve and its vulnerability to an unexpected repair.
- You tested the access requirement directly: after the client said same-day access mattered, you checked whether Goal Saver’s several-day withdrawals would work; the client clearly said no for emergency money.
- You helped the client articulate a useful distinction between an immediate-access emergency reserve and a separate planned savings goal.

**What was missed**

- Suitability conflict first: your final recommendation puts all emergency money in Goal Saver despite the client explicitly rejecting its several-day withdrawal delay for emergency funds.
- The QAR 9,000 certification goal in 18 months was never explored; no required average contribution or separate goal visibility was discussed.
- Income and fixed bills were not established, and irregular expenses plus contribution flexibility—such as pausing or adjusting transfers when car maintenance or family travel hits—were not assessed, so affordability is unsupported.

**How to improve**

- Correct the recommendation: do not assign emergency money to Goal Saver; keep an immediate-access reserve, and use Goal Saver only for the separate certification goal if the client accepts delayed withdrawals and possible bonus forfeiture; verify the terms.
- Ask what the savings goal is, its amount and deadline, then calculate and discuss whether about QAR 500 per month is feasible after bills and irregular expenses.
- Ask about monthly take-home pay and fixed bills, then plan adjustable or pausable Goal Saver transfers with a review after costly months. Optional product alternative: Everyday Access Account for the emergency reserve.

[Recommendation screen](deployed_app_evaluation_after_fixes_assets/mohamed-unsuitable-recommendations.png) · [Coach result screen](deployed_app_evaluation_after_fixes_assets/mohamed-unsuitable-feedback.png).

## Evidence and final recommendation

- [Structured results and genuine downloaded report contents](deployed_app_evaluation_after_fixes.json).
- [Original evaluation, preserved](deployed_app_evaluation.md).
- [Desktop selection](deployed_app_evaluation_after_fixes_assets/desktop-selection.png).
- [Mobile Maryam selection](deployed_app_evaluation_after_fixes_assets/mobile-touch-maryam.png).
- [Mobile Mohamed selection](deployed_app_evaluation_after_fixes_assets/mobile-touch-mohamed.png).

**Final acceptance:** Three of four scenarios completed, not all four. Both strong interviews received grounded, fair feedback. Mohamed’s unsuitable recommendation was identified in the correct section; Maryam’s was not verified because Coach validation exhausted. Student state and downloads were preserved correctly, no timeout recurred, and the mobile overlap fix was observed.

**Submission recommendation: HOLD final signoff.** Resolve AF01 and verify owner-visible deployment revision evidence. Then explicitly authorize a limited follow-up for the same failed Maryam scenario. Successful scenarios need not be repeated automatically. The observed functional improvements are substantial, but one required training workflow still cannot deliver coaching.

Exact backend revision remains unverified despite the matching public stylesheet and updated error path. Human numerical rubric ratings remain unassigned. One run per scenario does not establish statistical AI reliability or rule out other model errors.

No application code, credentials, deployment settings, original evaluation files, commits or pushes changed during this task. Only these evaluation reports and student-visible screenshot assets were created. No AI calls were made after the 24-attempt round, and the browser was closed.
