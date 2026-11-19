# Phase 2.6 behavioral evaluation

All ten existing scenarios have genuine interview and coach records. Workflow completion and JSON validation are separate from human quality approval. All numerical ratings remain unscored.

## Coverage and observed response lengths

| Case | Evidence | Feedback words | Review status |
| --- | --- | --- | --- |
| maryam-strong | [Phase 2.6 live case](phase2_6_maryam_strong.json) | 225 | [Unscored review](phase2_6_maryam_strong.review.md) |
| maryam-weak | [Phase 2.6 live case](phase2_6_maryam_weak.json) | 274 | [Unscored review](phase2_6_maryam_weak.review.md) |
| maryam-unsuitable | [Phase 2.6 live case](phase2_6_maryam_unsuitable_rechecked.json) | 201 | [Unscored review](phase2_6_maryam_unsuitable_rechecked.review.md) |
| maryam-natural | [Prior live client transcript with refreshed Coach](phase2_6_maryam_coach_only.json) | 280 | [Unscored review](phase2_6_maryam_coach_only.review.md) |
| maryam-product | [Phase 2.6 live case](phase2_6_maryam_product.json) | 251 | [Unscored review](phase2_6_maryam_product.review.md) |
| mohamed-strong | [Phase 2.6 live case](phase2_6_mohamed_strong.json) | 239 | [Unscored review](phase2_6_mohamed_strong.review.md) |
| mohamed-weak | [Phase 2.6 live case](phase2_6_mohamed_weak.json) | 232 | [Unscored review](phase2_6_mohamed_weak.review.md) |
| mohamed-unsuitable | [Phase 2.6 live case](phase2_6_operator_mohamed_unsuitable.json) | 222 | [Unscored review](phase2_6_operator_mohamed_unsuitable.review.md) |
| mohamed-natural | [Phase 2.6 live case](phase2_6_mohamed_natural.json) | 208 | [Unscored review](phase2_6_mohamed_natural.review.md) |
| mohamed-product | [Carried forward from Phase 2.5](phase2_5_mohamed_product.json) | 393 | [Unscored review](phase2_5_mohamed_product.review.md) |

## Request and token accounting

Agent-issued calls in this task — 37. Reported usage — {'prompt_tokens': 69889, 'completion_tokens': 26973, 'total_tokens': 96862}.

A preserved operator-generated Mohamed unsuitable case adds 4 requests and 9877 reported total tokens. Retained Phase 2.6 verification evidence therefore represents 41 requests and 106739 total tokens.

The operator reused the original output path across cases. An earlier Maryam unsuitable record was observed with 4 requests and 10,262 total tokens before that path was overwritten. It is excluded from retained workflow coverage and the 41-request evidence total. Account usage may also include operator runs outside this task. Historical Phase 2.5 calls are excluded from current-task usage.

## Engineering observations

- The eight newly covered cases produced final feedback from 201 to 274 words, averaging 231.5. The 180–260-word target is soft. Maryam weak remains slightly above it.
- On the same Maryam natural transcript, earlier refined feedback was 410 words and the new Coach output is 280 words. The prior Mohamed product feedback remains a 393-word historical comparison and was reused without extra requests.
- Both unsuitable cases identify conflicts with explicitly stated client constraints. The strong cases credit actual discovered figures and acknowledged product limitations.
- Initial Maryam unsuitable feedback wrongly criticized omission of an unselected, undiscussed cash-management product. That output is retained in phase2_6_maryam_unsuitable.json. A narrow validation check and bounded real-model repair now guard this category. The saved coach-only recheck removes that criticism and frames the alternative as optional.
- Natural follow-ups retain the goal amount, distinguish income from expenses, and avoid making every private fact available after a vague question.
- Some advice can still overlap, and conditional alternatives can be phrased more strongly than ideal. No human 4/5 acceptance result has been claimed.

## Human review

Open each accompanying .review.md packet. It contains numbered transcript evidence, the submission, selected-product limitations, private predefined-need checklists, and eleven blank criteria. Mark needs fully discovered, partially discovered, or missed. Rate applicable criteria from 1 to 5 with a target of at least 4, citing evidence. Use the offline --ratings workflow documented in README to save a reviewed copy.

These notes describe inspected behavior. They are not model-generated numerical grades or a substitute for human review.
