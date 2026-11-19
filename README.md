# Bank Client Discovery Simulator

**Phase 2.6 · AI quality checks and human behavioral review**

The simulator is a banking education project. Students interview a fictional client, identify financial needs and constraints, and justify one or more product recommendations. The assignment assesses discovery skills, including how students follow up on incomplete answers and explain trade-offs in their recommendations.

Phase 1 provides validated content, interview state, and recommendation services. Phase 2 adds a real AI Client, an AI Coach, a shared Ollama Cloud adapter using the official OpenAI Python SDK, and a disclosure controller. Phase 2.5 refines question relevance, conversational follow-ups, product discussions, and coaching fairness. Phase 2.6 adds concise coaching guidance, targeted contextual matching, systematic scenario coverage, and explicit human review records. The adapter connects directly to the cloud through its OpenAI-compatible endpoint. See [Ollama API compatibility](https://docs.ollama.com/api/openai-compatibility). Phase 3 will add the Streamlit interface, followed by deployment in Phase 4 and end-to-end testing and submission in Phase 5.

## Setup

Install Python 3.11 or later. From the repository root, create a virtual environment, install the package and test dependencies, and run pytest.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
```

After dependency installation, the test suite runs offline and requires no API key. The editable install lets you import the backend from outside the repository and reflects edits to the source and JSON files.

### Configuration

Phase 1 tests run without an API key. For local AI configuration, run the following command from the repository root. It creates `.env` from `.env.example` only when `.env` does not exist.

```sh
if [ ! -e .env ]; then
    cp -n .env.example .env
fi
```

Open `.env` in your editor and replace `your_ollama_cloud_api_key` with your Ollama Cloud API key. The selected cloud model is `deepseek-v4.1-flash`.

```dotenv
AI_API_URL=https://ollama.com/v1
AI_API_KEY=your_ollama_cloud_api_key
AI_MODEL=deepseek-v4.1-flash
```

`load_settings()` uses python-dotenv to read the repository `.env` and gives process environment variables precedence. The default endpoint is `https://ollama.com/v1` and the default model is `deepseek-v4.1-flash`. Set `AI_MODEL` to change it. `require_ai_configuration()` validates the URL, key, and model when constructing the shared API adapter. Keys and placeholder values are checked only when AI integration is initialized.

`.env` may contain your actual API key, so committing it would expose credentials through the repository and its history. Git ignores `.env`, its local variants, and `.streamlit/secrets.toml`. Keep `.env.example` in version control with its placeholder key. Check the exclusions without displaying credentials.

```sh
git check-ignore -v .env .env.local .streamlit/secrets.toml
git ls-files -- .env
```

The second command should produce no output. Settings mask the API key in their representation and JSON output. To check presence in application code, inspect `bool(settings.ai_api_key.get_secret_value().strip())` and display only the resulting boolean.

#### Future Streamlit Community Cloud configuration

The local `.env` is read by python-dotenv on your computer. For deployment, enter the following root-level TOML values in the app's **Streamlit Community Cloud Secrets settings**, replacing the placeholder with the actual key there. Keep the actual key out of GitHub.

```toml
AI_API_URL = "https://ollama.com/v1"
AI_API_KEY = "your_ollama_cloud_api_key"
AI_MODEL = "deepseek-v4.1-flash"
```

Streamlit exposes root-level secrets as environment variables. These entries belong at the TOML root, so the backend can continue using `load_settings()` without importing Streamlit. A local `.streamlit/secrets.toml` is an optional file managed by Streamlit, while this backend's local setup reads `.env`. See [Streamlit secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management) and [Community Cloud secrets settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Architecture

### Phase 2.5 review findings

The earlier live sample exposed several conversation-quality issues. A broad working-capital rule made available cash, upcoming obligations, expected receipts, and the calculated gap available together. The client then volunteered the full set of figures instead of answering only the relevant parts of the question. The controller tracked unlocked facts without distinguishing current relevance from what had actually been said. Contextual follow-ups lacked explicit matching support. Client requests carried neither catalogue product descriptions nor editable personality guidance. The coach's saved feedback also treated discussion of unselected financing alternatives as a missing requirement and repeated figures across several sections.

Python services validate content and manage the workflow directly in process. Pydantic validates the JSON, session state, and agent contracts. `python-dotenv` reads local configuration, and pytest exercises the backend without an external service.

```text
src/bank_simulator/
  config.py                      Environment settings and AI readiness validation
  models.py                      Content, session, and agent models
  data_loader.py                 JSON schema, identifier, and reference checks
  evaluation.py                  Offline feedback measurements and human review packets
  services/
    content_service.py           Public catalogue and private client lookup
    interview_service.py         Client selection, transcript, and session lifecycle
    recommendation_service.py    Needs summary, product choices, and justifications
    coaching_context.py          Private coaching context assembly
    ai_workflow.py               Full AI turns and validated coaching feedback
  agents/
    interfaces.py                AI Client and AI Coach protocols
    api_adapter.py               Shared Ollama Cloud connection and safe errors
    disclosure.py                Question matching and private fact filtering
    client_agent.py              Fictional customer roleplay
    coach_agent.py               Evidence-based coaching and JSON validation
data/
  clients/{maryam,mohamed}.json      Public client profiles
  hidden_needs/{maryam,mohamed}.json  Private facts and disclosure guidance
  products.json                  Five fictional banking products
tests/                           Offline pytest suite
scripts/smoke_test_ai.py          Explicit live API and behavior check
scripts/manual_interview.py       Interactive terminal interview and coaching
scripts/evaluate_conversations.py Individual live conversation evaluation
scripts/conversation_scenarios.json Scripted student inputs for ten evaluation cases
.env.example                     Optional AI settings template
pyproject.toml                   Package metadata and test configuration
requirements.txt                 Editable install with test dependencies
```

### Editing content

- Edit `data/clients/` for names, backgrounds, public financial situations, and interview opening contexts. Students can see these fields when selecting a client.
- Edit `data/hidden_needs/` for financial facts, preferences, constraints, personality guidance, and discovery expectations. Each private `client_id` must match one public `id`. Keep `personality_guidance` limited to tone and conversational habits. Store financial revelations in referenced facts, so personality text does not bypass disclosure control.
- Each disclosure topic contains human-readable guidance, `question_patterns`, and `fact_references`. References identify a private section and a zero-based list index. Update indices when reordering facts. `answer_patterns` can narrow which available facts address the current question. `follow_up_patterns` together with `follow_up_after` identify contextual questions following named topics. `response_patterns` recognize which topic's facts the customer actually mentioned. `product_ids` makes a relevant preference or concern available when a catalogue product is introduced. All patterns are case-insensitive regular expressions. Validation checks patterns, fact indices, predecessor topics, and product IDs. Split facts and rules when only part of a topic should be disclosed.
- Edit `data/products.json` to change the fictional products, their suitability, or their limitations. Keep all product IDs unique. If an ID changes, update any `related_product_ids` in the private discovery expectations.
- Create a new `ContentService` after editing files to load the updated content. Run `python -m pytest` to verify the schemas and included cases. All products and financial situations are fictional and intended for education.

## Developer guide

The interview moves through `draft`, `active`, and `completed`. Selecting a client starts the interview. Only an active interview accepts messages. After ending it, the student submits a needs summary and at least one product with a justification. The recommendation service verifies IDs and keeps the student's wording, so the coach can evaluate even an unsuitable choice.

```python
from bank_simulator.services.content_service import ContentService
from bank_simulator.services.interview_service import InterviewService
from bank_simulator.services.recommendation_service import RecommendationService
from bank_simulator.agents.api_adapter import OllamaCloudAdapter
from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow

content = ContentService()
interviews = InterviewService(content)
recommendations = RecommendationService(content)

adapter = OllamaCloudAdapter()
try:
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    session = interviews.create_session("mohamed")
    session = workflow.send_student_message(session, "What are you saving for?")
    # Repeat send_student_message for each question, keeping the returned snapshot.
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, "My understanding of the client's savings goal.")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="goal-saver-account", justification="A separate account for the dated goal.",
    )])
    feedback = workflow.generate_feedback(session)
finally:
    adapter.close()
```

- **AI Client.** `OllamaClientAgent` implements `AIClientAgent.respond()`. The workflow builds the private context internally, the agent filters it, and `InterviewService` records the generated response. User messages map to API `user` messages and previous client replies map to `assistant` messages. The prompt favors around 1–3 natural sentences for ordinary questions and longer answers when a multipart question warrants them. Editable personality guidance distinguishes the clients. The client uses a temperature of 0.5 and keeps its verified 2,048-token ceiling, including any model reasoning. The coach uses 0.1 and its verified 8,192-token ceiling.
- **AI Coach.** `OllamaCoachAgent` implements `AICoachAgent.evaluate()`. The workflow requires a completed interview, a summary, and recommendations before assembling the complete private context. A separate coaching prompt asks for transcript evidence, missed and partially discovered needs, and suitability analysis of the actual submitted choices against the full catalogue. Feedback validates as `CoachFeedback` with **What went well**, **What was missed**, and **How to improve**. The coach requests JSON-object mode with an 8,192-token completion ceiling, then independently validates the three sections with Pydantic. Markdown JSON fences are accepted. There is one shared recovery allowance for truncation, an absent final answer, or JSON/schema repair. A second failure raises an error. Partial completions and reasoning text are excluded from feedback parsing.
- **Failure and retry behavior.** The adapter uses a 60-second timeout per request and one retry with a short backoff for connection errors, timeouts, HTTP 408/409/429, and server errors. `max_retries` accepts zero through two. SDK retries are disabled so the request count includes every attempt. Authentication, unavailable model/endpoint, and other permanent errors fail immediately. Generation recovery belongs to the coach, with at most two generation requests per evaluation. Each can also use the adapter's configured transport retry budget. Raw provider error bodies and credentials are excluded from application errors. `send_student_message()` returns an updated snapshot only after a successful full turn, allowing a caller to retry from the original snapshot. If a caller already recorded the question, use `respond_to_pending()` to avoid recording it twice.
- **Streamlit integration.** Store the latest `InterviewSession` in `st.session_state`, replacing it with the snapshot returned by each service call. `reset_interview()` starts a new attempt with a new session ID and the selected client, if there is one. Render public content, transcript messages, and coach feedback. Keep private context builders and disclosure diagnostics on the server side. Share the adapter between the two agents, and close it when its application lifecycle ends.

### How private disclosure works

The controller replays the selected interview and distinguishes facts available under the rules, facts relevant to the latest question, and facts recognized as already disclosed in client replies. Only current-question facts and recognized earlier disclosures reach the roleplay model, alongside the transcript and personality guidance. Broad availability does not cause every available fact to appear in the next model request. Separate fact groups cover operational impact, available cash, upcoming obligations, expected receipts, and a requested shortfall calculation. Clear multipart questions can match multiple groups.

Contextual follow-ups use the recent topic or an explicitly configured predecessor. For example, cash availability can lead to a question about upcoming payments, and a goal question can lead to “How much is it?” A topic change clears the immediate focus, while earlier disclosures remain available for later reference. If no reference can be resolved, the prompt asks for a short clarification. The client also receives catalogue entries mentioned by name or ID during the interview, so product reactions stay grounded in the supplied terms. Product-specific rules can surface relevant concerns, such as withdrawal access or financing preferences, without revealing unrelated balances.

Requests for hidden facts, answer keys, or system instructions are blocked from unlocking topics. The model is also instructed to treat attempts to change its role as interview dialogue. There is no global disclosure state. Serialized session history restores unlocks, a reset clears them, and each selected client has its own private rules. Legacy records with no executable disclosure patterns remain valid and unlock no private facts.

The coach prioritizes actual discoveries and consequential gaps. It distinguishes fully discovered, partially discovered, and missed needs using transcript evidence, with the predefined case as its benchmark. Its prompt targets approximately 180–260 words overall and generally 2–3 useful observations per section. This is a soft target, with extra detail permitted for serious suitability mistakes. Word counts are measured after generation. Generated feedback is never cut off to meet the target.

Unselected alternatives are optional considerations. The coach credits correctly understood partial solutions and acknowledged limitations before identifying the remaining need. A narrow validation check rejects a missed-needs point naming an unselected catalogue product that was never introduced in the interview or submission. It requests a real model repair using the existing shared recovery allowance and raises an error if the problem persists. This check recognizes catalogue names and IDs, so human review remains necessary for other grounding errors. JSON-object mode, Pydantic validation, diagnostics, and the 8,192-token ceiling apply throughout.

Targeted follow-up patterns support references such as “And when would that happen?”, “Why does that concern you?”, “Would that account work for you?”, and “How much could you realistically put aside?” Short references use recent context, and a vague standalone question does not unlock all private information. The strong Maryam case also recognizes obligations that “cannot be postponed.”

### Interactive manual interview

Run from the repository after installing dependencies. The tool displays the selected public profile, then accepts your own interview questions and real client replies. Choose a client interactively or specify an ID.

```sh
python scripts/manual_interview.py --live --client maryam --output /tmp/maryam-manual.json
python scripts/manual_interview.py --live --client mohamed --output /tmp/mohamed-manual.json
```

Use `/end` to finish the interview, write your needs summary, choose one or more catalogue IDs, and provide justifications. Genuine coach feedback appears under the three required headings. After a failed client request, `/retry` retries the pending question from the last valid session snapshot. A failed coach request also permits an explicit retry. `--output` saves completed turns and any submitted work even if a call fails or you interrupt the session. Public profile data, conversation, catalogue products, and feedback form the student-facing view.

### Individual conversation evaluations

Ten editable cases cover strong discovery, weak discovery, unsuitable recommendations, natural follow-ups, and product discussion for each client. List them without making API calls, then explicitly select one case per invocation.

```sh
python scripts/evaluate_conversations.py
python scripts/evaluate_conversations.py --live --scenario maryam-natural \
    --output /tmp/maryam-natural.json
python scripts/evaluate_conversations.py --live --scenario mohamed-product \
    --output /tmp/mohamed-product.json
```

Cases contain script-authored student questions and submissions. Client replies and coach feedback come from the real API. The listing previews normal and maximum request counts. Reports include genuine transcripts, selected products, safe diagnostics, usage, word counts, and eleven unscored criteria. Each JSON result also produces a `.review.md` packet with numbered messages, actual submissions, catalogue limitations, and predefined-need checklists. The private reference section is for the reviewer, so keep these packets outside the student chat view.

Run `python scripts/evaluate_conversations.py --coverage` to list saved and pending cases. Coverage requires a valid completed session, matching client and student-question sequence, and structured coach feedback. Failed attempts are shown separately. A recorded workflow or valid JSON does not establish coaching accuracy.

### Record human rubric scores

Review five client criteria: realism, gradual disclosure, financial consistency, memory/follow-ups, and product discussion. Review six coach criteria: discovered needs, missed needs, product suitability, evidence grounding, usefulness, and conciseness. Score each applicable area from 1 to 5, aiming for at least 4. A 1 means major failures, 3 means usable with noticeable issues, and 5 means consistently convincing and grounded behavior. Use N/A only when an area genuinely does not apply, such as product discussion in a conversation that never introduced a product.

Create an offline packet and a blank ratings template from an existing report.

```sh
python scripts/evaluate_conversations.py \
    --review-report samples/phase2_6_maryam_weak.json \
    --review-output /tmp/maryam-review.md \
    --ratings-template /tmp/maryam-ratings.json
```

Read the transcript and submission first. Mark important predefined needs fully discovered, partially discovered, or missed, citing message numbers. Check the selected product against stated constraints and catalogue limitations. Distinguish an acknowledged limitation from an unresolved need. Then edit the ratings JSON manually: enter numeric scores under `scores`, set `applicable` to false with a null score for N/A, and add message references or explanations under `evidence`. The optional `reviewer` field identifies the human reviewer.

Save those human-supplied ratings into a copy of the report.

```sh
python scripts/evaluate_conversations.py \
    --review-report samples/phase2_6_maryam_weak.json \
    --ratings /tmp/maryam-ratings.json \
    --output /tmp/maryam-reviewed.json \
    --review-output /tmp/maryam-reviewed.md
```

Scores stay null until explicitly supplied. No model grades its own conversation. The local tool validates score ranges and reports whether the human-supplied ratings meet the 4/5 target. It preserves the original transcript and feedback. Word counts and exact-duplicate-point counts are diagnostic measurements, not quality ratings; related or unsupported statements still need human assessment.

The standard smoke test remains a short reliability check. Individual conversation cases explore behavior and may require more client turns. Live use requires `--live`; the tools disable transport retries and retain the coach's single recovery allowance. Run only the cases needed for the current investigation.

### Phase 2.6 verification and comparison

All 204 offline tests pass, retaining the original 168. Added coverage includes the six observed follow-up failures, discovery-classification and concision instructions, all ten scenarios' context isolation, human-rating validation, offline review copies, coverage accounting, exact-duplicate diagnostics, and bounded product-fairness repair. No pytest test makes a live request.

The operator chose all eight previously untested cases after seeing their normal 39-request estimate and 47-request maximum. Runs proceeded one case at a time. A valid operator-generated Mohamed unsuitable result was preserved and reused, so that case needed no duplicate calls from the agent. The earlier two Phase 2.5 client conversations were reused, with a coach-only refresh for Maryam's natural case.

All ten cases now have genuine interview and coach records, with no live-coverage cases pending. The [Phase 2.6 evaluation summary](samples/phase2_6_evaluation_summary.md) links each selected result, its word count, request accounting, and review notes. Each corresponding `.review.md` packet provides eleven blank criteria and transcript references. The [blank ratings template](samples/phase2_6_human_ratings_template.json) can be copied and filled manually. Human 4/5 acceptance remains pending because no person has supplied ratings.

The eight newly covered cases produced final feedback averaging **231.5 words**, with a **201–274** range. Seven were within the 180–260-word soft target. On the same saved Maryam natural interview, feedback fell from **410 to 280 words**. That result remains slightly above target. The carried-forward Mohamed product report remains a 393-word historical comparison and was not regenerated.

One important coaching error was investigated before continuing: initial Maryam unsuitable feedback treated failure to consider an unselected, undiscussed product as a mistake. That genuine output is retained in [the initial result](samples/phase2_6_maryam_unsuitable.json). A targeted validation guard now uses the existing recovery allowance for this category, and [the coach-only recheck](samples/phase2_6_maryam_unsuitable_rechecked.json) correctly rejects interest-bearing credit while placing the alternative in optional improvements. Feedback is regenerated by the model rather than silently edited.

The agent issued **37 requests**, consuming **96,862 reported total tokens**. The reused operator result represents **4 requests and 9,877 tokens**, making the retained verification evidence **41 requests and 106,739 tokens**. A separate earlier operator Maryam result was observed with four requests and 10,262 tokens before its output path was reused. It is excluded from retained coverage and the 41-request evidence total. The summary distinguishes historical calls and external runs from the agent's calls.

Natural follow-ups preserved the goal amount, income/expense context, and receipt timing without unlocking every private fact. Strong cases received credit for actual figures and constraints, while weak and unsuitable cases surfaced material omissions or conflicts. The concise outputs can still contain overlapping advice or optional considerations phrased too strongly. JSON validity, word counts, and the narrow product guard provide useful checks, but human evidence review remains the acceptance step.

Before future live testing, list cases and estimates, choose only needed IDs, and inspect each report before continuing. Use unique output paths to preserve evidence. API calls can consume provider allowance even when a request fails; reported token usage is recorded without making a currency-cost estimate. Reuse saved interviews for coach-only checks when the conversation itself does not need retesting.

### Phase 2.5 verification

At the end of Phase 2.5, all 168 offline tests passed, including the original 140. Those tests cover prompt guidance, current-question disclosure, multipart questions, contextual follow-ups, recognition of prior disclosures, product context, editable personalities, rule validation, and terminal retry/export behavior. These deterministic tests check the inputs and state the application controls. They do not assert an exact generated sentence or prove all possible conversational behavior.

Limited live verification used `deepseek-v4.1-flash` for two selected cases and one coach-only refinement check.

| Live run | Requests | Reported total tokens | Result |
| --- | --- | --- | --- |
| Maryam natural conversation | 6 | 13,912 | Five complete client turns and validated feedback |
| Mohamed product discussion | 5 | 12,066 | Four complete client turns and validated feedback |
| Maryam coach-only refinement | 1 | 9,287 | Validated feedback with unselected financing framed as optional |

The controlled verification used twelve requests and 35,265 reported total tokens. No recovery requests were needed. The original and refined coach responses are retained for comparison. The remaining eight evaluation cases are available individually and were not run as part of this limited verification. Numerical rubric scores remain blank for human inspection.

Maryam answered the operational-impact question without volunteering amounts. She gave only the available balance when asked for cash, then answered both obligations and incoming receipts in a multipart follow-up. When Business Flex Credit was raised, she expressed her Sharia preference and used the catalogue terms. Mohamed separated certification money from emergency access, reacted to Goal Saver's withdrawal delay, and asked about the bonus. He did not volunteer an emergency balance when asked about consequences of a car bill. The coach correctly identified that balance as still undiscovered.

The first Maryam feedback still repeated the funding-gap issue and treated an unselected alternative as a missing discussion. The refined prompt moved that alternative into an optional improvement and credited the acknowledged no-financing limitation. Its response decreased from 460 to 410 words, but still exceeded the approximate 200–350-word guidance and contained some overlapping advice. Mohamed's feedback was 393 words. Concision and redundancy remain points for human review.

Genuine examples are saved as [Maryam's natural conversation](samples/phase2_5_maryam_natural.json), [Mohamed's product discussion](samples/phase2_5_mohamed_product.json), and [Maryam's refined coach feedback](samples/phase2_5_maryam_coach_refinement.json). They include actual client and coach output, script-authored student submissions, request counts, and usage. The two evaluation reports also contain the unscored human-review rubric. The separately authored illustrative interview below serves a different purpose.

### Offline tests and live verification

```sh
python -m pytest
```

Tests block socket connections and use scripted agent outputs or the real SDK with an injected HTTP mock transport. They cover errors and bounded retries, disclosure input boundaries, context construction, coach repair, state transitions, and atomic session updates.

The following explicit command makes real API calls using the local configuration and may consume your provider allowance.

```sh
python scripts/smoke_test_ai.py --live
```

It asks Maryam three questions, submits a student summary and a cash-management recommendation, and validates genuine coach feedback. It usually makes four API calls, with a fifth allowed for one coach recovery. Transport retries are disabled for the smoke test. Output distinguishes API connectivity from narrow behavioral checks, reports the configured and API-reported models, counts attempted requests, and totals reported token usage. Exit code 0 means the API workflow and all basic behavioral checks passed, 1 indicates a configuration or API failure, and 2 indicates a behavioral check requiring review.

To save a genuine example for later submission, including the transcript, student summary, recommendations, feedback, model, and call count, use an output file.

```sh
python scripts/smoke_test_ai.py --live --output /tmp/bank-simulator-live-example.json
```

Review the generated content before using it for the assignment. The illustrative dialogue below remains a separately authored example.

Use a saved report or serialized `InterviewSession` to debug the coach without replaying the client turns. The input is validated, including its client and product references, before an API adapter is created. Input, output, and diagnostic files must have different paths.

```sh
python scripts/smoke_test_ai.py --live \
    --coach-only samples/maryam_live_interview.json \
    --output /tmp/coach-result.json \
    --diagnostics /tmp/coach-diagnostics.json
```

`--diagnostics` is opt-in. It records response model, choice count, finish reason, content type and length, reasoning-field presence and length, token usage, and sanitized failure categories. Coach JSON/schema errors are distinguished from API response and SDK failures. JSON error locations and schema field names are recorded without response values. The diagnostic report contains metadata only. The optional output report contains the interview and, on success, genuine feedback. Failed coach requests also save the completed interview so it can be retried. Reasoning traces, prompts, credentials, and HTTP headers are excluded from both reports.

### Coach reliability diagnosis

The original generic "incomplete or unsupported response" error was raised whenever the first API choice had a finish reason other than `stop`, before the coach attempted JSON parsing. A controlled coach-only reproduction on the saved interview returned `finish_reason="length"` and used all 4,096 completion tokens. The response contained a 16,791-character reasoning field and 3,773 characters of partial final content. The historical failed response was unavailable, so its exact finish reason cannot be independently verified.

A recovery experiment with an 8,192-token ceiling produced a complete response with `stop`, but its final content failed JSON validation. The coach now requests documented JSON-object mode and starts with the verified 8,192-token ceiling. It keeps one bounded recovery request and validates every final response with the existing Pydantic model. The prompt requests concise, focused feedback and retains the instruction to credit limitations already acknowledged by the student. Reasoning controls remain model-defined. The implementation uses the provider's defaults and reads only final assistant content. See [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) and [thinking controls](https://docs.ollama.com/capabilities/thinking).

The initial Phase 2 verification on 19 November 2026 used `deepseek-v4.1-flash`, also confirmed by the API response model field. It completed three client turns and one validated coach response in four API calls, with all basic behavioral checks passing. Maryam's introduction stayed public, the cash-flow question elicited the predefined figures, and the financing-preference question elicited her Sharia requirement. The first coach response contained a contradictory criticism about a limitation already stated in the justification. After strengthening the grounding instruction, one additional coach-only request against the saved interview credited that acknowledgement and focused on missing contingency planning. That initial verification used five live requests.

The subsequent reliability investigation also used `deepseek-v4.1-flash` and completed the following controlled runs.

| Run | Requests | Result |
| --- | --- | --- |
| Original 4,096-token coach-only reproduction | 1 | Truncated at the token ceiling |
| Larger-budget recovery experiment | 2 | Recovered from truncation, then rejected malformed final JSON |
| Fixed coach with JSON-object mode | 1 | Complete, validated feedback |
| Full interview with the final fix | 4 | Three client turns and validated feedback; all basic checks passed |

The reliability investigation used eight requests and 37,967 reported total tokens across successful and failed generations. The final full run used 9,296 total tokens and required no recovery. The coach credited the student's explicit acknowledgement that cash management supplies no financing and identified missing contingency planning and purchase-documentation questions. At the end of that investigation, the offline suite had 140 passing tests, including all original 116 tests.

The saved [live interview and genuine coach feedback](samples/maryam_live_interview.json) includes the actual transcript, script-authored student summary and recommendation, model, request count, and usage. Its [successful response diagnostics](samples/maryam_live_diagnostics.json), [truncation reproduction](samples/coach_truncation_diagnostics.json), and [failed JSON recovery experiment](samples/coach_json_failure_diagnostics.json) contain safe metadata for review. The sample can also be used as the validated input for `--coach-only`.

### Known limitations

- Disclosure matching and recognition of prior disclosures use the English patterns authored in the JSON. Novel paraphrases, negations, product nicknames, and ambiguous follow-ups can be missed or matched too broadly. The transcript still preserves actual replies even when a response pattern misses one. Topic-level groups can contain closely related facts, so authors should split rules when partial disclosure matters. Add focused patterns and tests when expanding the cases.
- Filtering controls the private facts supplied to the model. Generated wording, consistency, and resistance to novel prompt-injection attempts still require review. A student can introduce unsupported claims in the transcript. The client prompt instructs the model to avoid confirming them.
- Coach schema validation enforces structure. Assessing the accuracy and grounding of its comments requires behavioral evaluation. The smoke test's keyword and amount checks are limited signals, and offline mocks verify code paths and evidence delivery.
- JSON-object mode improves formatting, but Pydantic validation is still mandatory. Reasoning and output length vary between calls, so even the 8,192-token ceiling and one recovery can be exhausted. A provider timeout, rate limit, or invalid response still surfaces as a failure with the saved interview available for another explicit attempt.
- Calls are synchronous, and full transcript history is sent each turn. Long interviews can exceed provider context limits. An uncertain network timeout may have consumed a request even though the session snapshot stays unchanged. Reusing an older successful snapshot can generate another reply, so a frontend must keep the newest snapshot and serialize requests per interview.
- The backend returns sanitized errors and never logs credentials. Keep SDK and HTTP debugging disabled when handling live settings and interview data.

## Sample interview with Mohamed

This illustrative dialogue and submission were written for the README.

| Student | Mohamed |
| --- | --- |
| What would you like to work on today? | My salary is steady, and I’d like a clearer plan for my bills and savings. |
| What comes in each month, and which expenses are fixed? | I take home QAR 8,000. About QAR 4,600 goes to fixed bills before groceries and the occasional big expense. |
| What kinds of bigger expenses come up, and how much have you set aside for them? | Car repairs and family travel can wipe out what I’d usually save. I only have QAR 1,200 set aside for emergencies. |
| How quickly would you need those funds if a repair bill came up? | I’d want access the same day. I couldn’t count on being able to wait several days for a withdrawal. |
| Is there a separate goal with an amount and a deadline? | I want to save QAR 9,000 in 18 months for a professional certification course and exam. |
| That works out to QAR 500 a month on average. How predictable is the amount left after your other expenses? | It varies. I’d like to check what’s left after essentials and emergency savings, then adjust or pause the goal transfer in expensive months. |

**Student needs summary.** Mohamed needs same-day access to emergency funds and separate savings of QAR 9,000 for certification in 18 months. The goal requires an average of QAR 500 per month. Check whether that fits after essentials, irregular expenses, and emergency contributions before setting up a transfer.

**Student recommendations**

- **Everyday Access Account.** Build the emergency reserve in the instant-access space so Mohamed can pay an unexpected bill the same day. Check whether card or transfer limits could affect a larger payment.
- **Goal Saver Account.** Use adjustable transfers for certification fees once the budget supports them. Review progress after expensive months. Early withdrawals take several business days, so keep emergency money in the other account.

After submission, the backend assembles the full transcript, Mohamed’s private case, the catalogue, and the student's summary and justifications for the AI Coach.
