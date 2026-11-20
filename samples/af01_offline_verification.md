# AF01 — targeted validator correction and offline verification

Date: 20 November 2026 (Asia/Qatar).

**Status: offline implementation verified; deployed AF01 acceptance remains pending.** The full suite passes: **307 tests**, retaining the previous 267 and adding 40 cases. No paid API calls, commit, push or deployment occurred. Existing evaluation reports and screenshots were not overwritten.

## Established facts and uncertainty

The deployed `maryam-unsuitable` record contains three successful Client turns, the exact original student submission, two counted Coach attempts, a generic repair-exhaustion error and `coach_feedback: null`.

The code establishes that the final attempt raised `CoachingGroundingError`: either the unselected-product check or the suitability-section check. The record does not identify which. The first attempt's reason is unknown: the bounded loop can recover from schema/grounding failure or certain unusable generations. Neither rejected body nor per-attempt validation reason was recorded in the available AF01 evidence.

The web path constructed the Coach without an optional diagnostic sink, and the Coach previously emitted no default reason-level server log. This observability gap is confirmed. Historical model noncompliance versus validator error **cannot be established retrospectively** without the missing responses/check results. No model or provider failure is assumed.

The following validator defects were independently reproduced using clearly labelled authored offline feedback, not recovered AI outputs:

- Valid criticism such as “Business Flex Credit contradicts her explicit refusal of conventional financing” was rejected because the old check required both `Sharia`/`Islamic` and `interest` in the same point.
- A valid correction such as “Do not recommend the interest-bearing facility; discuss a financing arrangement she would accept” was rejected without a repeated exact product name or Sharia wording.
- A point's criticism of the selected product could be incorrectly applied to a nearby optional alternative, because the old fairness check searched the entire point together.
- “Business Flex Credit has no conflict with Sharia requirements despite its interest charges” was accepted because the check recognized conflict keywords without their negation.

These are confirmed code bugs and plausible contributors to AF01, **not proof of its historical trigger**.

## Targeted correction

Grounding now resolves a unique submitted conflict from its supported financial description and the actual Client requirement. It accepts clear equivalents without requiring one sentence or literal product-name wording. A point naming a different product cannot substitute for the selected conflict.

Criticism is evaluated by sentence/clause, including a neighbouring optional suggestion introduced with “while,” “whereas” or “but.” Actual unselected-product omissions are still rejected; labelling a demanded product “optional” does not excuse making it mandatory. Genuine cash-gap critique and criticism of actual student product discussions remain available.

Known conflict denials and explicit reversals of the Client's refusal are rejected. Acknowledging a cash-flow benefit while identifying the financing conflict remains valid. The conflict must still appear in `what_was_missed`; a distinct practical correction must still appear in `how_to_improve`. Copied criticism does not satisfy both sections.

A conservative QAR evidence guard also rejects clear unsupported currency claims and benchmark-only figures credited as discoveries. Supported figures, straightforward sums/differences and explicitly hypothetical improvement questions remain permitted. This is not a general financial or arithmetic grader; nonnumeric factual correctness still requires model compliance and review.

The repair request now describes the specific failed requirement and section, rather than giving only a generic product-fairness instruction. No feedback is inserted, moved, dropped or fabricated by application code.

## Safe developer diagnostics

Each attempted Coach generation records the following metadata through the existing optional sink. Failures also emit a default server-side warning, so the deployed web path does not need a frontend callback:

| Field | Meaning |
|---|---|
| `stage` | `coach_generation` versus `coach_feedback`, distinguishing API/generation failure from validation. |
| `attempt_index` | `0` for initial generation, `1` for the sole repair/recovery attempt. |
| `validation_failure_category` | Existing broad category, such as `suitability_sections`, `unselected_product_critique`, `invalid_schema` or `invalid_json`. |
| `reason_code` | Precise result, such as `missing_suitability_conflict`, `missing_distinct_correction`, `required_unselected_product`, `contradicted_requirement` or unsupported financial/discovery figure. |
| `failed_section` | One of the three feedback sections, `feedback` for a general failure, or null for success. |
| `rule_id` | Stable rule identifier: `sharia_financing`, `emergency_liquidity`, `optional_product_omission`, `financial_evidence`, `feedback_schema` or `usable_final_answer`. |
| `elapsed_seconds` | Monotonic elapsed time for that generation and validation attempt. |

Logs contain codes, section names, attempt index and elapsed time only. They do not contain student names, session identifiers, credentials, raw exceptions, prompts, profiles, product descriptions, response bodies or reasoning. Schema diagnostics retain only safe error types, allowlisted field names and numeric JSON error locations. They are not added to student reports or screens.

## Constraints preserved

- Pydantic `CoachFeedback` structure and validation remain intact.
- At most two model attempts: initial generation and one shared repair/recovery allowance.
- Both Coach completion ceilings remain 8,192 tokens.
- No changes to model, timeouts, API adapter, credentials, client records, product terms, Streamlit design or student workflow.
- No automatic user-level retry, extra model evaluator, new dependency or manually generated feedback.

## Offline verification

Run from the repository root with the existing virtual environment activated:

```bash
python -m pytest -q
```

Executed here as `.venv/bin/python -m pytest -q`: **307 passed in 2.87 seconds**. All pytest tests remain offline. Existing diagnostics assertions were updated to require the enriched metadata with deterministic timing, retaining their previous exact category/location and privacy checks.

The 40 new cases cover financing and correction paraphrases, missing/misplaced conflicts, copied explanations, optional alternatives, genuinely unresolved cash needs, wrong-product substitution, negated/inverted conflicts, unsupported financial/discovery figures, supported calculations, hypothetical questions, both clients' suitability requirements, API-versus-validation diagnostics, and initial-failure/repair-exhaustion logging without response bodies.

Existing tests continue to cover strong interviews, original recommendation wording, immutable workflow state, request accounting, no duplicate rerun calls, and bounded schema repair.

Saved genuine feedback was replayed locally through the validator without model requests:

| Saved evidence | Scenario | Result |
|---|---|---|
| Original deployed evaluation | Maryam strong | Rejected: `required_unselected_product`, `what_was_missed`. |
| Original deployed evaluation | Maryam unsuitable | Rejected: `missing_suitability_conflict`, `what_was_missed`. |
| Post-fix deployed evaluation | Maryam strong | Accepted unchanged. |
| Post-fix deployed evaluation | Mohamed strong | Accepted unchanged. |
| Post-fix deployed evaluation | Mohamed unsuitable | Accepted unchanged. |

There is no accepted or rejected raw AF01 candidate available to replay. Authored test fixtures are not presented as genuine model feedback.

## Exact files for review and a later commit/push

1. [Coach instructions, repair and diagnostics](../src/bank_simulator/agents/coach_agent.py).
2. [Grounding logic](../src/bank_simulator/agents/coaching_validation.py).
3. [Existing Coach diagnostic assertions](../tests/test_ai_coach.py).
4. [New AF01 regression tests](../tests/test_af01_validation.py).
5. This offline verification note.

The preceding `deployed_app_evaluation_after_fixes.md`, JSON and screenshot directory remain separate, untracked evaluation evidence from the prior task. They were preserved; review them separately when choosing what to commit. No Git write operations were performed here.

## Remaining limits and authorized follow-up

The rules remain lightweight, contextual pattern checks. Novel phrasing, complex financial assertions or ambiguous references can still need review. Passing the offline suite does not prove a particular live response will succeed, and AF01 must not be marked resolved on the deployed website yet.

A Coach-only diagnostic using a validated saved Maryam submission would be justified if separately authorized: one generation, or at most two including the existing repair, with safe diagnostics enabled. It would isolate Coach behavior but would not substitute for deployed Streamlit acceptance. No such call was made.

After review, an explicitly authorized commit/push and confirmation that the new revision is deployed, authorize **only `maryam-unsuitable`** through the actual deployed website:

1. Start a fresh browser session at [the deployed app](https://bank-client-discovery-simulator.streamlit.app/).
2. Use the unchanged three questions, summary, Business Flex Credit selection and justification from `scripts/conversation_scenarios.json`.
3. Require genuine Client replies and accepted Coach feedback; inspect the refusal conflict under What was missed and distinct corrective guidance under How to improve.
4. Verify no mandatory unselected-product critique, exact submitted wording, request counts and a complete student-report download.
5. Stop after this one scenario: **at most five AI attempts** (three Client replies plus one Coach generation and at most one repair), no manual retries. If it fails, preserve safe per-attempt diagnostics and stop.
6. Save genuine new evidence under a new filename without overwriting either previous evaluation. Report PASS, PARTIAL PASS or FAIL only from actual observations.

No follow-up live test is automatically authorized by this offline implementation. Final deployed acceptance remains pending that explicitly authorized retest.
