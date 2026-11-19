# Bank Client Discovery Simulator

**Phase 2 · Python backend with Ollama Cloud agents**

The simulator is a banking education project. Students interview a fictional client, identify financial needs and constraints, and justify one or more product recommendations. The assignment assesses discovery skills, including how students follow up on incomplete answers and explain trade-offs in their recommendations.

Phase 1 provides validated content, interview state, and recommendation services. Phase 2 adds a real AI Client, an AI Coach, a shared Ollama Cloud adapter using the official OpenAI Python SDK, and a disclosure controller. The adapter connects directly to the cloud through its OpenAI-compatible endpoint. See [Ollama API compatibility](https://docs.ollama.com/api/openai-compatibility). Phase 3 will add the Streamlit interface, followed by deployment in Phase 4 and end-to-end testing and submission in Phase 5.

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

Python services validate content and manage the workflow directly in process. Pydantic validates the JSON, session state, and agent contracts. `python-dotenv` reads local configuration, and pytest exercises the backend without an external service.

```text
src/bank_simulator/
  config.py                      Environment settings and AI readiness validation
  models.py                      Content, session, and agent models
  data_loader.py                 JSON schema, identifier, and reference checks
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
.env.example                     Optional AI settings template
pyproject.toml                   Package metadata and test configuration
requirements.txt                 Editable install with test dependencies
```

### Editing content

- Edit `data/clients/` for names, backgrounds, public financial situations, and interview opening contexts. Students can see these fields when selecting a client.
- Edit `data/hidden_needs/` for financial facts, preferences, constraints, and discovery expectations. Each private `client_id` must match one public `id`. Each disclosure topic contains human-readable guidance, `question_patterns`, and `fact_references`. Patterns are case-insensitive regular expressions matched against student messages. References identify a private section and a zero-based list index. Update indices when reordering facts. Validation rejects missing references, invalid patterns, patterns that match empty text, and incomplete pattern/reference pairs.
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

- **AI Client.** `OllamaClientAgent` implements `AIClientAgent.respond()`. The workflow builds the private context internally, the agent filters it, and `InterviewService` records the generated response. User messages map to API `user` messages and previous client replies map to `assistant` messages. The system prompt restricts the model to short first-person answers based on available scenario facts.
- **AI Coach.** `OllamaCoachAgent` implements `AICoachAgent.evaluate()`. The workflow requires a completed interview, a summary, and recommendations before assembling the complete private context. A separate coaching prompt asks for transcript evidence, missed and partially discovered needs, and suitability analysis of the actual submitted choices against the full catalogue. Feedback validates as `CoachFeedback` with **What went well**, **What was missed**, and **How to improve**. Markdown JSON fences are accepted. Invalid JSON or schema content gets at most one model repair request, followed by a clear error if validation still fails.
- **Failure and retry behavior.** The adapter uses a 60-second timeout per request and one retry with a short backoff for connection errors, timeouts, HTTP 408/409/429, and server errors. `max_retries` accepts zero through two. SDK retries are disabled so the request count includes every attempt. Authentication, unavailable model/endpoint, and other permanent errors fail immediately. Empty or truncated responses fail visibly. Raw provider error bodies and credentials are excluded from application errors. `send_student_message()` returns an updated snapshot only after a successful full turn, allowing a caller to retry from the original snapshot. If a caller already recorded the question, use `respond_to_pending()` to avoid recording it twice.
- **Streamlit integration.** Store the latest `InterviewSession` in `st.session_state`, replacing it with the snapshot returned by each service call. `reset_interview()` starts a new attempt with a new session ID and the selected client, if there is one. Render public content, transcript messages, and coach feedback. Keep private context builders and disclosure diagnostics on the server side. Share the adapter between the two agents, and close it when its application lifecycle ends.

### How private disclosure works

The controller reconstructs unlocked topics by replaying student messages in the selected interview transcript. A direct question or a supported paraphrase matches an editable pattern and unlocks only the facts referenced by that rule. Previously unlocked facts remain available for follow-ups. Introductory questions receive only the public profile. Rules and answer keys stay out of the roleplay request. The coach receives the complete private record through its own context builder.

Requests for hidden facts, answer keys, or system instructions are blocked from unlocking topics. The model is also instructed to treat attempts to change its role as interview dialogue. There is no global disclosure state. Serialized session history restores unlocks, a reset clears them, and each selected client has its own private rules. Legacy records with no executable disclosure patterns remain valid and unlock no private facts.

### Offline tests and live verification

```sh
python -m pytest
```

Tests block socket connections and use scripted agent outputs or the real SDK with an injected HTTP mock transport. They cover errors and bounded retries, disclosure input boundaries, context construction, coach repair, state transitions, and atomic session updates.

The following explicit command makes real API calls using the local configuration and may consume your provider allowance.

```sh
python scripts/smoke_test_ai.py --live
```

It asks Maryam three questions, submits a student summary and a cash-management recommendation, and validates genuine coach feedback. It usually makes four API calls, with a fifth allowed only to repair malformed feedback. Transport retries are disabled for the smoke test. Output distinguishes API connectivity from narrow behavioral checks, reports the configured and API-reported models, and counts attempted requests. Exit code 0 means the API workflow and all basic behavioral checks passed, 1 indicates a configuration or API failure, and 2 indicates a behavioral check requiring review.

To save a genuine example for later submission, including the transcript, student summary, recommendations, feedback, model, and call count, use an output file.

```sh
python scripts/smoke_test_ai.py --live --output /tmp/bank-simulator-live-example.json
```

Review the generated content before using it for the assignment. The illustrative dialogue below remains a separately authored example.

The live test on 19 November 2026 used `deepseek-v4.1-flash`, also confirmed by the API response model field. It completed three client turns and one validated coach response in four API calls, with all basic behavioral checks passing. Maryam's introduction stayed public, the cash-flow question elicited the predefined figures, and the financing-preference question elicited her Sharia requirement. The first coach response contained a contradictory criticism about a limitation already stated in the justification. After strengthening the grounding instruction, one additional coach-only request against the saved interview credited that acknowledgement and focused on missing contingency planning. Total live API requests for implementation verification were five.

### Known limitations

- Disclosure matching supports the English paraphrases authored in the JSON. Unrecognized wording, negations, and ambiguous follow-ups can miss a relevant topic or unlock one too broadly. A matching rule unlocks its referenced group together. Add focused patterns and tests when expanding the cases.
- Filtering controls the private facts supplied to the model. Generated wording, consistency, and resistance to novel prompt-injection attempts still require review. A student can introduce unsupported claims in the transcript. The client prompt instructs the model to avoid confirming them.
- Coach schema validation enforces structure. Assessing the accuracy and grounding of its comments requires behavioral evaluation. The smoke test's keyword and amount checks are limited signals, and offline mocks verify code paths and evidence delivery.
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
