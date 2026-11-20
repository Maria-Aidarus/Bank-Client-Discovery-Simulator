# Deployed application evaluation

**Application:** [Bank Client Discovery Simulator](https://bank-client-discovery-simulator.streamlit.app/)  
**Date:** 20 November 2026, 12:57–13:14 (Asia/Qatar, UTC+03:00)  
**Overall result: PARTIAL PASS.** Two genuine Maryam workflows completed. Mohamed’s strong scenario stopped after an AI response timeout; Mohamed’s unsuitable scenario was not started. The deployment is functional, but this round does not establish full final-submission readiness.

## Environment and method

Playwright controlled headless Google Chrome 158.0.8127.36 on macOS. Desktop was 1440 × 1000; mobile was 390 × 844, including a separate touch-enabled browser context. All generations were requested through the deployed Streamlit interface. No local backend responses, mocked agents or older transcripts were substituted.

Existing definitions in [conversation_scenarios.json](../scripts/conversation_scenarios.json) supplied the exact student questions, summaries, selections and justifications. Student inputs are scripted; Client replies and Coach feedback below are genuine outputs captured from the deployed website. Planned inputs for incomplete scenarios are not represented as submitted work.

The configured provider/model is Ollama Cloud / `deepseek-v4.1-flash`, according to project configuration. The student interface did not expose the returned model identifier, deployed commit, token usage or provider logs; these were not independently verified.

## Scenario results and request budget

| Scenario | Result | Client attempts | Coach attempts | Outcome |
|---|---|---:|---:|---|
| maryam-strong | PARTIAL PASS | 7 | 1 | Complete workflow; one coaching fairness concern (C01). |
| maryam-unsuitable | PASS | 3 | 1 | Complete workflow; unsuitable financing correctly flagged. |
| mohamed-strong | FAIL | 4 | 0 | Three replies; fourth request timed out. Partial export preserved. |
| mohamed-unsuitable | NOT RUN | 0 | 0 | Testing stopped after the timeout. |

**16 of 30 permitted AI attempts**, based on the sum of visible per-interview request counters (8 + 4 + 4). There were 13 successful Client replies, one failed Client attempt and two successful Coach outputs. No manual AI retry or scenario replay occurred. Each completed Coach used one counted attempt; no Coach recovery request was observed. Provider-side counts/billing and tokens were unavailable.

Further live calls stopped after the website reported a timeout, following the instruction to stop when availability prevents progress. No blanket provider outage is inferred from this single failure. Subsequent form, mobile, restart and session-isolation checks made no AI calls.

## Deployment, UI and privacy checks

- Both public client cards loaded. All five product accordions displayed terms matching `data/products.json`, including eligibility, limitations and unsuitable uses.
- Desktop selection, interview, recommendation and feedback screens were exercised. Mobile selection, sidebar catalogue, chat-input visibility and two-product recommendation fields were checked; no horizontal overflow was measured. The mobile hosting badge overlap is recorded as U01.
- Empty summary/product/justification errors appeared beside the relevant fields. Only selected products had visible justification fields. Deselecting and reselecting restored the exact draft; an extra deselected product was absent from the actual submitted/exported recommendation.
- Two separate justifications rendered and retained their values for Mohamed’s two-product draft. This draft was **not submitted for coaching** after the live stop. Deployed two-product Coach evaluation therefore remains unverified.
- Each successful turn preserved the previous transcript in order, adding one student message and one response. Loading indicators were observed on multiple Client calls and both Coach submissions. They were not reliably sampled on the fastest calls.
- Downloads and form edits did not increase the visible request counter. Restarts, client switching and a separate browser context showed fresh state. This does not prove protection against every concurrent click or network-reconnection race.
- The failed request retained six completed messages, showed a Retry question button and labelled the unanswered question as outside the saved transcript. The failed question was absent from the export, and no feedback was fabricated. Retry execution was deliberately not tested.
- Three downloaded JSON reports contained only public identity, observed transcript, submitted work and actual feedback (where completed). No unexpected hidden-needs/disclosure metadata, API credential fields, system prompts or raw reasoning were observed. Coach feedback may appropriately discuss fictional missed needs after evaluation.
- Errors were sanitized. No server credentials were requested, opened or extracted. This is a student-surface check, not an exhaustive security or adversarial prompt-injection audit.

The Cloud shell produced nonblocking 403/404 console/resource errors for `/api/v1/app/event/open`, `/api/v2/user/details`, and Heap analytics scripts. No page-level JavaScript exception was captured. Both Maryam workflows completed despite these messages; they are not evidence of the AI timeout cause.

Automation adjustments: the initial heading lookup targeted the hosting frame rather than the app iframe; multiselect popovers required Escape before other fields; a download-help tooltip needed dismissal before switching clients. These driver obstacles did not consume AI requests and are not counted as confirmed application defects.

## Findings, ranked by severity

### HIGH — D01: One deployed AI Client request timed out and blocked scenario completion

**Observed:** In mohamed-strong, question four ("How quickly would you need access to that money?") produced "The AI request timed out. Please try again." after 60.648 seconds. The sidebar showed 3/30 questions and 4/40 requests.

**Expected:** A genuine response to the contextual follow-up, or a clearly reported recoverable failure. Error reporting and data preservation worked, but the requested end-to-end scenario could not complete in this run.

**Reproduction:** 1. Start a fresh Mohamed interview. 2. Ask the first three questions from mohamed-strong. 3. Ask the fourth access question and observe the result. This describes the observed sequence; repeatability is not established.

**Frequency:** Once in 14 Client request attempts (16 total AI attempts); not retried.

**Cause:** UI timeout verified; underlying provider, network, model-latency or server-side cause NOT VERIFIED. No provider logs, status code or token usage were available through the student interface.

**Investigate:** src/bank_simulator/agents/api_adapter.py (60-second default timeout); src/bank_simulator/ui/controller.py (sanitized failure and request accounting); Cloud/provider request diagnostics, if available to the operator.

**Recommendation:** Investigate safe server-side timing/error metadata before changing timeouts or retry policies. Then explicitly authorize a limited retry and complete both Mohamed scenarios. Preserve the working retry UX and immutable transcript behavior.

### MEDIUM — C01: Strong-interview feedback treats an unselected trade-finance explanation as an omission

**Observed:** Maryam strong selected only Business Cash Management, explicitly acknowledging that it supplies no funding and that a separate contingency is needed. The Coach nevertheless listed "The Sharia trade-finance coverage boundary was not tested" under What was missed, while placing Islamic Trade Finance under an Optional improvement.

**Expected:** Critique the genuinely unresolved funding contingency, while keeping additional education about an unselected product an optional improvement. The product limitation itself is catalogue-correct; the concern is evaluation scope and fairness.

**Reproduction:** 1. Run maryam-strong with its predefined questions, summary and sole Cash Management recommendation. 2. Inspect the third What was missed point and the Optional trade-finance improvement. Output is stochastic; repeatability is not established.

**Frequency:** Observed once in two completed Coach outputs.

**Cause:** Output behavior verified. Exact prompt/validation cause NOT VERIFIED.

**Investigate:** src/bank_simulator/agents/coach_agent.py: product-fairness instructions and _validate_product_critique.

**Recommendation:** Review the distinction between a missed underlying need and explaining an unselected product, including category-level references such as trade finance. Keep all existing structured-feedback validation.

### LOW — U01: Streamlit hosting badges overlap the lower mobile viewport

**Observed:** At 390 x 844 in a fresh touch-enabled mobile context, hosting badges overlapped the lower part of the first client card and its Start interview area. No horizontal overflow was found; the mobile catalogue and recommendation fields were usable.

**Expected:** Primary controls remain unobscured at common mobile viewport positions.

**Reproduction:** 1. Open the hosted root URL in a fresh 390 x 844 mobile viewport. 2. Inspect the bottom edge of the initial client-selection screen.

**Frequency:** Observed in the fresh mobile screenshot; not tested on physical devices.

**Cause:** Visual overlap verified. Hosting chrome may be outside application control.

**Investigate:** src/bank_simulator/ui/views.py: mobile spacing; Streamlit Community Cloud hosting chrome.

**Recommendation:** Review mobile spacing/viewport behavior and any supported hosting-chrome options. This is polish rather than a demonstrated workflow blocker.

No CRITICAL issue was observed. D01 is a single verified workflow interruption, not a claim of persistent outage. C01 concerns coaching fairness rather than an incorrect product term.

## Genuine scenario evidence

### maryam-strong — PARTIAL PASS

**Workflow:** PASS: seven student questions, seven genuine Client responses, exact submitted summary and recommendation, all three Coach categories and a downloaded report.

**Client assessment:** Financial amounts and timing matched the scenario. Only relevant business facts were disclosed; Sharia preference appeared after the financing question. The Client reacted to Cash Management without selecting products or calculating the student's full solution.

**Coach assessment:** Credited cash-flow discovery, payroll, Sharia preference, and the explicitly acknowledged no-funding limitation. Correctly identified missing invoice terms and an unspecified funding contingency. However, framed an unselected trade-finance coverage explanation as a missed requirement (finding C01).

**Student 1:** How do late customer payments affect your business?

**AI Client:** When customers pay late, it can leave us short of cash for payroll and supplier invoices, which makes day-to-day operations tight. Since we’re considering larger retail orders, I’d like to understand how to manage that timing risk better.

**Student 2:** How much cash is available, and what payments are due?

**AI Client:** The business currently has QAR 25,000 in available cash, and we have QAR 40,000 in supplier and payroll payments due over the next three weeks.

**Student 3:** What payments are you expecting from customers, and when?

**AI Client:** We’re expecting QAR 60,000 from outstanding customer invoices over the next four to six weeks, though I can’t pin down the exact receipt dates yet. That uncertainty is part of why I want to review our banking arrangements before taking on larger orders.

**Student 4:** Which obligations cannot be postponed?

**AI Client:** Payroll is the one with fixed dates—it can’t be postponed. The supplier payments are also coming due, but payroll is the obligation I know has no flexibility on timing.

**Student 5:** What financing arrangements would you accept?

**AI Client:** I wouldn’t take a conventional interest-bearing credit facility. I’d be open to a Sharia-compliant arrangement, but I’d need the structure explained clearly first—how the bank earns its return, and what fees or penalties may apply—before I’d consider it.

**Student 6:** Do you have supplier quotations or purchase orders for the larger orders?

**AI Client:** No, I don’t have either a supplier quotation or a purchase order for the larger retail orders yet. That’s part of why I want to understand the timing and structure carefully before committing.

**Student 7:** Business Cash Management can track invoices and upcoming payments but supplies no funding. Would that help?

**AI Client:** It could help with the visibility side—tracking overdue invoices and seeing upcoming supplier payments—but since it doesn’t provide funding, it won’t solve the cash gap by itself. I’d want to understand how dependable the projected balances are when my receipt dates are still uncertain.

**Actual submitted needs summary:**

The business faces a possible QAR 15,000 timing gap. Follow up collections and fixed obligations, preserve the Sharia requirement, and establish a contingency for delayed receipts. Purchase finance needs qualifying documentation.

**Actual submitted recommendations:**

- **Business Cash Management** (`business-cash-management`): Useful for collections and payment visibility. It does not fund the gap, so a separate contingency is required.

**Genuine AI Coach feedback** (273 whitespace-delimited words):

**What went well**

- Elicited the core cash-flow facts efficiently: late customer payments, QAR 25,000 cash, QAR 40,000 due in three weeks, and QAR 60,000 expected over four to six weeks with uncertain dates; the summary correctly calculates a possible QAR 15,000 gap.
- Confirmed payroll is the fixed obligation and that Maryam would decline conventional interest-bearing credit; the summary preserves her Sharia-compliant requirement.
- Proposed Business Cash Management only for invoice and payment visibility, explicitly noting it provides no funding; also noted no supplier quotation or purchase order and that purchase finance needs qualifying documentation.

**What was missed**

- Payment timing was only partly explored: late payment and uncertain receipts were established, but not the 30-day invoice terms, the 45–60-day payer behaviour, invoice aging, current collections tracking, or which customers repeatedly pay late.
- The contingency for the calculated gap remains undefined: there was no discussion of how payroll and suppliers would be covered if expected receipts slipped, despite the summary recommending a contingency.
- The Sharia trade-finance coverage boundary was not tested: while documentation was noted, the transcript does not clarify that such finance is tied to an eligible goods purchase and cannot cover existing payroll or supplier bills.

**How to improve**

- Ask: “Which invoices are overdue, by how long, which customers routinely pay late, and how do you currently track or control supplier payment timing?” Use that to prioritise collections and visibility needs.
- Ask: “If that gap occurs, what non-interest options would you use—supplier timing, reserves, or faster collections?” and record the agreed contingency.
- Optional: reassess Islamic Trade Finance only for future stock purchases once a supplier quotation or purchase order exists, explaining its structure and that it does not solve the current operating gap.

**Not verified:** Novel paraphrases or adversarial prompt attacks beyond the scripted questions.

### maryam-unsuitable — PASS

**Workflow:** PASS: three student questions, three genuine Client responses, unsuitable-but-valid product accepted, all three Coach categories and a downloaded report.

**Client assessment:** Rejected conventional interest-bearing Business Flex Credit after clearly stating the Sharia preference. No contradictory figures or automatic alternative product selection were observed.

**Coach assessment:** Explicitly said Business Flex Credit is unsuitable because Maryam rejected interest-bearing facilities. Correctly distinguished discovered cash/preferences from missed receipts, fixed payroll dates and purchase documentation. Optional alternatives were identified as optional.

**Student 1:** How much business cash is available and what payments are due?

**AI Client:** We have QAR 25,000 in available business cash, and QAR 40,000 in supplier and payroll payments coming due over the next three weeks. That timing is part of why I want to review our banking arrangements.

**Student 2:** What preferences or restrictions do you have about financing?

**AI Client:** I’d decline a conventional interest-bearing credit facility. I prefer Sharia-compliant banking, and I’d want to understand how the structure works before considering any financing.

**Student 3:** Business Flex Credit is an interest-bearing revolving line. Would that work for you?

**AI Client:** No, that wouldn’t work for me because it’s interest-bearing. I’d rather look at Sharia-compliant options and understand the structure before deciding whether any financing is appropriate.

**Actual submitted needs summary:**

Maryam has a short-term cash gap and requires Sharia-compliant arrangements.

**Actual submitted recommendations:**

- **Business Flex Credit** (`business-flex-credit`): A flexible credit line can cover upcoming bills despite the stated preference.

**Genuine AI Coach feedback** (223 whitespace-delimited words):

**What went well**

- You established the key liquidity figures: QAR 25,000 cash against QAR 40,000 of supplier and payroll payments due within three weeks, making a near-term gap visible.
- You directly asked about financing preferences and uncovered that Maryam declines interest-bearing credit and prefers Sharia-compliant banking.

**What was missed**

- You did not ask when customers pay, so the late-payment pattern (45–60 days against 30-day terms) and the uncertain QAR 60,000 of expected receipts were not explored; the cash-gap assessment is therefore partial.
- You did not confirm that payroll has fixed dates and cannot be postponed, which affects how any shortfall should be handled.
- You did not explore expansion documentation: Maryam has no supplier quotation or purchase order, so eligibility for documented trade finance is unknown.
- You did not assess payment visibility or control, missing her wish to track overdue invoices and schedule supplier payments.

**How to improve**

- Do not recommend Business Flex Credit: Maryam explicitly rejected interest-bearing facilities, so this is unsuitable; limit suggestions to Sharia-compliant structures and explain that suitability still needs review.
- Next ask for invoice amounts, overdue customers, expected receipt dates and which payments are fixed, then quantify and stress-test the shortfall rather than relying on the summary.
- Optional: assess Business Cash Management for invoice tracking and projected balances—it does not fund the gap—and Islamic Trade Finance only for a documented eligible stock purchase, not existing payroll or bills.

**Not verified:** Other unsuitable products or alternate wordings.

### mohamed-strong — FAIL

**Workflow:** INCOMPLETE: three genuine responses; question four timed out. No completed recommendation submission or Coach feedback. A partial student report was downloaded.

**Client assessment:** Successful turns distinguished the QAR 9,000 certification target over 18 months, QAR 8,000 take-home pay, QAR 4,600 fixed bills before groceries/irregular expenses, and QAR 1,200 existing emergency savings. The access follow-up received no final response.

**Coach assessment:** NOT VERIFIED: Coach was not called for this scenario.

**Student 1:** What are you saving for, and what amount and deadline do you have in mind?

**AI Client:** I’m saving QAR 9,000 over 18 months for professional certification course and exam fees, and I want to keep that separate from my emergency fund.

**Student 2:** What income comes in, and what fixed bills go out each month?

**AI Client:** My salary is QAR 8,000 take-home each month. My fixed monthly bills come to about QAR 4,600, before groceries and irregular expenses.

**Student 3:** How much emergency money is set aside, and which irregular expenses come up?

**AI Client:** I have about QAR 1,200 set aside for emergencies. Car maintenance and family travel are the irregular expenses that can reduce—or sometimes wipe out—what I save in a month, and an unexpected repair could use most of that emergency cushion.

**Student 4:** How quickly would you need access to that money?

**Client:** No response received. The website displayed: “The AI request timed out. Please try again.” The failed question was not added to the saved transcript.

**Actual submitted summary/recommendations:** None. **Coach feedback:** None. The predefined future inputs are available in the structured report, clearly labelled as planned inputs.

**Not verified:** QAR 500 required contribution versus actual affordability.; Successful response to the contextual access follow-up.; Client reaction to the two proposed products.; Submitted two-product suitability and Coach fairness.

### mohamed-unsuitable — NOT RUN

**Workflow:** Not started: further paid testing stopped after the preceding timeout.

**Client assessment:** NOT VERIFIED in this deployed test round.

**Coach assessment:** NOT VERIFIED in this deployed test round.

**Actual submitted summary/recommendations:** None. **Coach feedback:** None. The predefined future inputs are available in the structured report, clearly labelled as planned inputs.

**Not verified:** Client response to restrictive savings for emergency funds.; Coach identification of the emergency-liquidity suitability conflict.

## Evidence files

- [Structured results, genuine downloaded report contents and exact planned inputs](deployed_app_evaluation.json).
- [Desktop selection](deployed_app_evaluation_assets/desktop-selection-final.png).
- [Fresh mobile selection and hosting-badge overlap](deployed_app_evaluation_assets/mobile-fresh-selection.png).
- [Mobile catalogue](deployed_app_evaluation_assets/mobile-fresh-catalogue.png).
- [Selected-product recommendation form](deployed_app_evaluation_assets/maryam-strong-recommendations.png).
- [Maryam strong feedback](deployed_app_evaluation_assets/maryam-strong-feedback.png).
- [Maryam unsuitable feedback](deployed_app_evaluation_assets/maryam-unsuitable-feedback.png).
- [Mohamed timeout and preserved history](deployed_app_evaluation_assets/mohamed-strong-timeout.png).
- [Two-product unsubmitted draft](deployed_app_evaluation_assets/multiple-product-draft.png).
- [Mobile recommendation fields](deployed_app_evaluation_assets/mobile-recommendations.png).

## Final assessment

**Core assignment features are demonstrably present:** two public clients, five fictional products, real Client conversations, student-controlled submissions, all three Coach categories and genuine downloadable complete examples. However, successful Mohamed coaching and the full four-scenario deployed acceptance check remain incomplete.

**Before final signoff:** investigate the timeout with safe operational evidence, review C01’s optional-product fairness, then run an explicitly authorized limited round completing Mohamed strong and Mohamed unsuitable. Do not infer a permanent outage, automatically retry, blindly increase limits or remove validation. Mobile badge polish can wait.

The successful Coach outputs were 273 and 223 words: one modestly above and one within the 180–260-word soft target. The strong output credited acknowledged limitations rather than falsely claiming they were ignored. The unsuitable output explicitly rejected the submitted conventional facility. The latter placed that critical suitability warning in How to improve after several discovery omissions; moving the key conflict earlier could improve emphasis.

Numeric human-review rubric scores remain unassigned. This is an evidence-based qualitative evaluation, not independent human grading. It covers one run per attempted scenario, one desktop browser family and emulated mobile views. Physical-device behavior, successful retry execution, real Coach failure recovery and adversarial disclosure resistance were not verified.

**Another live round is required. Overall deployment readiness: PARTIAL PASS, not unconditional submission approval.** No application source, configuration or deployment setting was changed. No commit or push was performed. Only evaluation reports and student-visible screenshots were added; the test browser was closed.
