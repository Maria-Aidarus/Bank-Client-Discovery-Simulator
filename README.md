# Bank Client Discovery Simulator

**Phase 1 · Tested Python backend**

The simulator is a banking education project. Students interview fictional clients, identify their needs and constraints, and justify product recommendations. Maryam's distribution business and Mohamed's personal savings goals provide distinct discovery exercises.

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

The backend uses python-dotenv to read an optional local `.env`. Process environment variables take precedence. Copy `.env.example` to `.env` only if `.env` does not exist and enter credentials in your local editor. Git excludes `.env` and local secret files. Keep the example in version control with its placeholder key.

```dotenv
AI_API_URL=https://ollama.com/v1
AI_API_KEY=your_ollama_cloud_api_key
AI_MODEL=your_selected_cloud_model
```

Phase 1 data loading and tests require no API key. `require_ai_configuration()` validates provider settings when AI integration is initialized.

## Architecture

Python 3.11+, Pydantic, python-dotenv, editable JSON, and pytest provide a modular backend that can be imported directly into a future Streamlit application.

```text
src/bank_simulator/
  config.py
  models.py
  data_loader.py
  services/
    content_service.py
    interview_service.py
    recommendation_service.py
    coaching_context.py
  agents/interfaces.py
data/
  clients/{maryam,mohamed}.json
  hidden_needs/{maryam,mohamed}.json
  products.json
tests/
.env.example
pyproject.toml
requirements.txt
```

### Editing content

Public files contain the information students see when choosing a client. Private files contain financial facts, constraints, preferences, disclosure guidance, and discovery expectations for the future agents. Public content methods return only public profile fields. Each private `client_id` must match a public `id`.

Edit the JSON to change a scenario or product. Keep identifiers unique and update private discovery expectations when referenced product IDs change. A new `ContentService` loads and validates the edited records. The products and scenarios are fictional and intended for education.

## Developer guide

Create a `ContentService`, then inject it into `InterviewService` and `RecommendationService`. Selecting a client moves a draft interview to active. Record student questions and externally supplied client replies, then end the interview. Submit a needs summary and product justifications before building coaching context. Unknown product IDs and incomplete submissions are rejected. Unsuitable catalogue choices are accepted for later critique.

Each service operation returns a new validated `InterviewSession` snapshot. The caller stores that state, which can later live in Streamlit session state. Resetting starts a new attempt with the selected client and a new session ID.

The `AIClientAgent` and `AICoachAgent` protocols define the future integration points. Client context carries the selected profile, private needs, and transcript. Coaching context adds the complete product catalogue, student summary, and recommendations. Phase 2 will add Ollama Cloud agents, followed by the Streamlit interface in Phase 3, deployment in Phase 4, and end-to-end verification in Phase 5.

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

After submission, the backend assembles the full transcript, Mohamed’s private case, the catalogue, and the student's summary and justifications for the future AI Coach.
