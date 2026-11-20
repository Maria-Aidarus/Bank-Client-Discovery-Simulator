# Targeted deployed-issue fixes — offline verification

Date: 20 November 2026 (Asia/Qatar).

**Status:** fixes implemented locally; 267 offline tests passed, retaining all 243 previous tests. No changes have been committed, pushed or deployed by this task. No paid requests or post-fix deployed scenarios have been run. The original deployed evaluation and its screenshots remain unchanged.

## Timeout investigation

The original Mohamed access follow-up failed after 60.648 seconds. The configured SDK timeout is 60 seconds; it applies to HTTP phases, rather than proving a strict total wall-clock deadline. Both SDK retries and adapter retries are disabled in the web path. The Coach's existing single content-recovery allowance is separate and does not retry a Client timeout.

The installed OpenAI SDK (2.54.0 in the development environment) wraps an underlying HTTP timeout as `APITimeoutError`. An offline HTTP-transport test confirms one attempted request, a safe error, unchanged successful transcript, and one added turn only after an explicit retry. This supports the observed failure mechanism but **does not establish why the deployed request stalled**. The original evidence contains no server-side timeout phase or provider trace. Provider latency, connection issues and other causes remain unverified; the model is not presumed broken.

The 60-second timeout and retry policies remain unchanged. One failure does not justify a longer wait or additional paid attempts. Increasing the limit would lengthen the busy period and would not diagnose the cause.

Existing diagnostic callbacks now include elapsed seconds. Timeout diagnostics identify only an allowlisted HTTP timeout class (connection/read/write/pool, or unknown). The web adapter writes failure-only metadata to server logs: category, elapsed time, HTTP status when available, and timeout phase. It does not log requests, responses, prompts, private profiles, reasoning, model settings, credentials or raw exception text. These measurements can support a later timeout decision if failures recur.

## Coach corrections

- Product grounding now recognizes catalogue-derived category references, including hyphenated trade finance and purchase finance. A generic future-finance statement in a summary no longer exempts a product from the optional-alternative check.
- An explanation of an unselected product is not automatically a required task. Genuine critique of an actual student product discussion remains allowed, as does direct critique of an unresolved funding contingency.
- Conservative checks identify the two explicit suitability conflicts from actual Client statements, submitted justifications and editable catalogue terms: required Sharia compliance versus interest-bearing financing; and emergency money assigned to delayed-withdrawal savings despite an immediate-access requirement. No client IDs, financial amounts or product-ID branches are embedded in this logic.
- A confirmed conflict must be identified in `what_was_missed`, with a distinct practical correction in `how_to_improve`. Merely moving the warning into advice or copying one explanation into both sections is rejected.
- A goal account alongside a separate accessible emergency reserve is not automatically unsuitable. Hidden benchmark facts alone do not prove that a student discovered a requirement.
- Invalid feedback uses the existing single model repair allowance. Repeated failure returns a safe error; points are never silently deleted, moved or fabricated. Pydantic validation and both 8,192-token Coach completion ceilings remain intact.

These checks cover known wording and financial concepts, not all possible financial judgments or paraphrases. The actual model must still be evaluated live; a valid JSON object is not proof of accurate or fair coaching.

Replaying the two original downloaded Coach outputs through the new validator offline reproduced both defects: Maryam strong was rejected as `unselected_product_critique`, and Maryam unsuitable as `suitability_sections`. This check made no model requests and does not represent new AI output.

## Mobile correction

A mobile-only rule reserves `3.5rem` plus the device safe-area inset beneath the application's client-selection scroll viewport. It targets the application's own client-card keys, without hiding hosting controls or selecting their internal elements. Desktop and interview layouts remain unchanged.

Offline Chrome/Playwright verification on the local app, with external browser requests blocked and no AI calls:

| Check | Observed result |
|---|---|
| Selection at 390 × 844 | Application scroll viewport ends at y=788, leaving a 56-pixel bottom strip. |
| Selected client button after scrolling into view | Button y=669.844, height=44; fully above the reserved strip. |
| Desktop at 1440 × 1000 | Application viewport remains 1440 × 1000. |
| Mobile interview | Full 390 × 844 viewport restored; chat input visible; counter 0/40. |

Actual hosted-badge behavior still needs post-deployment verification. The local test cannot certify the Cloud overlay fix. The temporary local browser and server were stopped after verification.

## Files and tests

Implementation: `agents/api_adapter.py`, `agents/coach_agent.py`, new `agents/coaching_validation.py`, `ui/controller.py`, and `ui/views.py` under `src/bank_simulator/`.

Tests: `tests/test_api_adapter.py`, `tests/test_web_app.py`, new `tests/test_coach_grounding.py`, and new `tests/test_timeout_recovery.py`.

Run from the repository root with the environment activated:

```bash
python -m pytest -q
```

Result: **267 passed**. The 24 added cases cover optional product/category fairness, remaining client needs, both suitability conflicts and required sections, repair exhaustion, separate goal/reserve suitability, timed SDK exceptions, failure-log privacy, explicit retry accounting, and Streamlit rerun/transcript preservation. Mobile geometry was checked through the local browser rather than asserting CSS source strings in pytest.

Client records, hidden needs, product terms, configuration, model, dependencies and deployment settings were not changed. The complete suite includes the existing local-environment and root-level Streamlit Secrets tests. Secret files remain ignored and untracked.

## Redeployment instructions — operator action required

These are instructions only; they have not been executed. Review the diff first. From the `main` branch, after activation:

```bash
python -m pytest -q
git diff --check
git add src/bank_simulator/agents/api_adapter.py \
  src/bank_simulator/agents/coach_agent.py \
  src/bank_simulator/agents/coaching_validation.py \
  src/bank_simulator/ui/controller.py \
  src/bank_simulator/ui/views.py \
  tests/test_api_adapter.py tests/test_web_app.py \
  tests/test_coach_grounding.py tests/test_timeout_recovery.py \
  samples/deployed_app_fix_notes.md
git commit -m "fix: enforce fair coaching sections and add safe timeout diagnostics"
git rev-parse HEAD
git push origin main
```

The original evaluation files are separate untracked evidence; review them before deciding whether to include them in a submission commit. Never stage `.env` or `.streamlit/secrets.toml`.

1. In Streamlit Community Cloud, confirm the existing app is connected to `Maria-Aidarus/Bank-Client-Discovery-Simulator`, branch `main`, entrypoint `app.py`. Leave its existing secrets and model unchanged.
2. Wait for the new commit to be built. Cloud normally updates from the connected GitHub branch automatically. If a restart is necessary, use the app's **Reboot** action; it interrupts active sessions. See [official app-management instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app) and [reboot instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app).
3. Record the commit from `git rev-parse HEAD` and verify the owner-visible build/deployment evidence corresponds to that revision. A working homepage alone does not establish which Coach implementation is running. If the deployed revision cannot be established, record it as unverified and do not claim post-fix acceptance.
4. Once the updated revision is confirmed, explicitly authorize the next live round. Use the actual [deployed app](https://bank-client-discovery-simulator.streamlit.app/), not the local backend.

## Pending post-deployment acceptance

All four post-fix scenarios are **NOT RUN**: `maryam-strong`, `maryam-unsuitable`, `mohamed-strong`, `mohamed-unsuitable`. This is not a new behavioral evaluation or a claim that the original timeout is resolved.

After explicit authorization, use the exact inputs in `scripts/conversation_scenarios.json` and a fresh isolated browser session for each scenario. Expected normal requests are 8 + 4 + 7 + 4 = 23; one built-in Coach recovery per scenario could raise that to 27. Enforce the overall 30-attempt limit, never silently retry, and stop if availability becomes unreliable.

Verify optional trade-finance treatment and remaining cash-flow needs for Maryam strong; conflict in What was missed plus correction in How to improve for both unsuitable scenarios; the previously failed access follow-up and complete two-product workflow for Mohamed strong. Check mobile badges, exports, request counts, preserved history and any regressions.

Preserve the original evaluation. Only after real testing, write the new observations to `samples/deployed_app_evaluation_after_fixes.md` and `samples/deployed_app_evaluation_after_fixes.json`. Record genuine responses, durations, errors and per-scenario outcomes. Until then, final deployed assignment acceptance remains pending.
