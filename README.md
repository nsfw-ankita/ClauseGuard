# RentRakshak 🏠

**Sign smart, not blind.**

RentRakshak is a simple Streamlit app that helps people understand rent agreements. It highlights risky clauses, missing important points, and suggests polite messages to ask the landlord for changes. It is designed for non-technical users, with simple language and Hindi/English support.

> **Disclaimer:** General guidance only, not legal advice.

## What it does

- Upload a rent agreement as **PDF**, **photo** (JPG/PNG), or **paste text**
- Detects whether the document looks like a rent agreement
- Uses **Gemini** to find red/yellow/green clauses in plain language
- Runs an independent **rules checklist** in code (English + Hindi keywords)
- Merges AI and rule findings, with no duplicate missing items
- Gives a **score out of 10** with label: Looks safe / Be careful / Risky
- Suggests **polite messages** you can copy and send to the landlord
- Generates a downloadable **PDF report**
- **Privacy:** processes agreement in memory only; does not save uploads

## Screenshots

<!-- Add screenshots here -->
- `screenshots/home.png` - Home screen
- `screenshots/results.png` - Results screen

## Project structure

```text
RentRakshak/
├── app.py                 # Streamlit UI
├── analyzer.py            # Input handling + Gemini analysis
├── rules.py               # Rule checklist + scoring
├── schemas.py             # Pydantic models
├── prompts.py             # Gemini prompt templates
├── report.py              # PDF report generation
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── samples/
│   ├── safe_agreement.txt
│   ├── risky_agreement.txt
│   └── missing_clauses_agreement.txt
└── tests/
    └── test_rules.py
```

## Windows setup

1. **Install Python 3.10+** from [python.org](https://www.python.org/downloads/windows/). During install, check "Add Python to PATH".
2. **Open PowerShell** and go to the project folder:

   ```powershell
   cd path\to\RentRakshak
   ```

3. **Create and activate a virtual environment**:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

4. **Install dependencies**:

   ```powershell
   pip install -r requirements.txt
   ```

5. **Create `.env`**:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env` and add your Gemini API key.

## Get a free Gemini API key

1. Go to [Google AI Studio API Keys](https://aistudio.google.com/app/apikey).
2. Sign in with your Google account.
3. Create an API key.
4. Put it in `.env` as `GEMINI_API_KEY=...`.
5. Check current model names at [Gemini API models docs](https://ai.google.dev/gemini-api/docs/models). Set `GEMINI_MODEL` in `.env` if needed.

## Run the app

```powershell
streamlit run app.py
```

The app opens in your browser (usually at `http://localhost:8501`).

## Demo mode (no API key)

Set in `.env`:

```env
MOCK_AI=true
```

This returns a fixed sample AI response so you can demo the app without an API key.

## How to test

```powershell
pytest
```

Tests cover rule checks, Hindi keyword detection, missing-clause merging, and score calculation.

## Rule checklist

The rules layer checks for:

- Security deposit amount
- Deposit refund timeline
- Notice period
- Lock-in period
- Rent increase cap
- Maintenance responsibility
- Eviction terms
- Police verification
- Electricity/water bill responsibility
- Property inspection and notice

## Scoring

- Start at **10**
- Each **red** clause: **-1.0**
- Each **yellow** clause: **-0.4**
- Each **missing rule item**: **-0.5**
- Minimum **0**, rounded to 1 decimal
- Labels: **8-10 Looks safe**, **5-7.9 Be careful**, **below 5 Risky**

## Limitations

- AI can make mistakes or miss clauses; always read the full agreement.
- Scanned/image quality affects extraction accuracy.
- Rule checks use keyword/regex matching and may not catch every legal nuance.
- Hindi support is for user-facing guidance; legal terms may vary by region.
- Not a substitute for a qualified lawyer.

## Future scope

- OCR fallback for low-quality scans
- Support for more regional languages
- State-specific rental rule hints
- Clause-by-clause comparison between two agreements
- Secure optional history with explicit user consent

## License

MIT - see [LICENSE](LICENSE).
