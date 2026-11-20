# *Bank Client Discovery Simulator!*

This is an AI-powered web application that helps students practise interviewing bank clients, identifying their financial needs, and recommending suitable banking products.

Students interact with fictional customers through an **AI Client**, explore banking products, and receive personalized feedback from an **AI Coach** on their interviewing skills and recommendations.

## Live Application

**[Launch the Bank Client Discovery Simulator](https://bank-client-discovery-simulator.streamlit.app)**

The application is hosted on Streamlit Community Cloud and can be accessed directly through a web browser. No installation, account, or API key is required to use the hosted version.

### How It Works

1. **Select a Client** — Choose between two fictional banking customers, Maryam and Mohamed, each with different financial situations and needs.
2. **Interview the AI Client** — Ask questions to understand the client's financial circumstances, priorities, and concerns. The AI Client responds conversationally and reveals relevant information as the interview progresses.
3. **Recommend Banking Products** — Explore five fictional banking products, select one or more recommendations, and briefly explain why they suit the client's needs.
4. **Receive AI Coaching** — The AI Coach reviews the interview and recommendations, then provides feedback in three areas:
   - **What went well:** Needs and considerations identified correctly.
   - **What was missed:** Important questions, financial needs, or unsuitable recommendations.
   - **How to improve:** Practical suggestions for stronger interviews and recommendations.

## Run Locally

The application can also be installed and run locally using your own OpenAI-compatible API connection.

### Prerequisites

- Python 3.11
- Git
- An Ollama Cloud API key or another compatible AI connection

### 1. Clone the Repository

```bash
git clone https://github.com/Maria-Aidarus/Bank-Client-Discovery-Simulator.git
cd Bank-Client-Discovery-Simulator
```

### 2. Create a Virtual Environment

**macOS / Linux:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

### 4. Configure the AI Connection

Copy the example environment file:

**macOS / Linux:**

```bash
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure your connection:

```dotenv
AI_API_URL=https://ollama.com/v1
AI_API_KEY=your_ollama_api_key_here
AI_MODEL=deepseek-v4.1-flash
```

The application was developed and tested using **Ollama Cloud** with `deepseek-v4.1-flash` through an OpenAI-compatible API.

The API URL, key, and model name are configurable. Local users must supply their own valid API credentials. The `.env` file is excluded from Git to prevent accidental exposure.

### 5. Start the Application

```bash
python -m streamlit run app.py
```

Open **http://localhost:8501** in your browser.

## Project Structure

```text
Bank-Client-Discovery-Simulator/
├── app.py                    Streamlit application
├── src/bank_simulator/
│   ├── agents/               AI Client and AI Coach
│   ├── services/             Interview and recommendation logic
│   └── ui/                   Streamlit interface
├── data/
│   ├── clients/              Public client profiles
│   ├── hidden_needs/         Private client information
│   └── products.json         Fictional banking products
├── samples/                  Example interview and feedback
├── tests/                    Automated tests
├── requirements.txt          Python dependencies
├── pyproject.toml            Package configuration
└── .env.example              API configuration template
```

Client profiles, hidden needs, and banking products are stored in separate editable JSON files, allowing the simulation content to be updated without changing the application code.

## Testing

Run the automated tests using:

```bash
python -m pytest -q
```

The automated test suite uses mocked AI responses and does not require live API requests.

## Sample Interview

A complete example of the simulation is available here:

**[View Sample Interview and AI Coach Feedback](samples/phase3_live_student_report.json)**

The example includes:

- Student–AI Client conversation
- Student's financial needs summary
- Banking product recommendation and justification
- AI Coach feedback

Student inputs were scripted for testing. AI Client responses and AI Coach feedback were generated using the configured AI model.

## Notes

- All client scenarios and banking products are fictional and intended for educational purposes.
- The application does not require user accounts or a database.
- Interview sessions are not permanently stored, but completed reports can be downloaded.
- AI-generated responses and feedback may contain errors.
- The hosted application uses securely configured API credentials; local installations require their own configuration.