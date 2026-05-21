# 🔍 AI Code Review Agent

An autonomous agent that clones a GitHub repository, parses Python source files using
Abstract Syntax Trees, and generates structured, confidence-rated review comments via
Google Gemini.

---

## Architecture

```
GitHub URL
    │
    ▼
┌─────────────┐     GitPython      ┌─────────────────┐
│  Ingestion  │ ───────────────▶   │  Cloned Repo    │
│ ingestion.py│ shallow clone      │  (local /tmp)   │
└─────────────┘                    └────────┬────────┘
                                            │ .py files
                                            ▼
                                   ┌─────────────────┐
                                   │    Parser       │
                                   │  parser.py      │
                                   │  Python `ast`   │
                                   │  → CodeChunks   │
                                   └────────┬────────┘
                                            │ batches of chunks
                                            ▼
                                   ┌─────────────────┐
                                   │    Reviewer     │
                                   │  reviewer.py    │
                                   │  Gemini Flash   │
                                   │  → JSON comments│
                                   └────────┬────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │   Streamlit UI  │
                                   │   app.py        │
                                   │  filter/download│
                                   └─────────────────┘
```

---

## Quick Start

### 1. Clone this repository

```bash
git clone https://github.com/<your-username>/ai-code-review-agent.git
cd ai-code-review-agent
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your API key

```bash
cp .env.example .env
# Open .env and paste your Gemini API key
```

Get a **free** Gemini API key at → https://aistudio.google.com/app/apikey

### 5. Run the app

```bash
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`.

---

## Usage

1. Paste a **public GitHub repository URL** (e.g. `https://github.com/psf/requests`)
2. Enter your **Gemini API key** in the sidebar (or pre-fill it in `.env`)
3. Click **Analyze Repo**
4. Use the sidebar filters to slice by severity, category, or confidence
5. Download results as JSON or CSV

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Ingestion | [GitPython](https://gitpython.readthedocs.io/) — shallow clone |
| Parsing | Python built-in `ast` module — functions, classes, imports |
| LLM | [Google Gemini 1.5 Flash](https://ai.google.dev/) — free tier |
| Orchestration | Custom Python pipeline (`agent/pipeline.py`) |
| Dashboard | [Streamlit](https://streamlit.io/) with custom CSS |
| Deployment | Streamlit Cloud / HuggingFace Spaces |

---

## Confidence Scoring

Every comment the agent generates includes a self-rated confidence score (0–100 %):

| Range | Meaning |
|-------|---------|
| 90–100 % | Certain — clear evidence in the code |
| 70–89 %  | Likely — context outside this chunk might change verdict |
| 50–69 %  | Possible — depends on wider codebase |
| 0–49 %   | Speculative — may be intentional |

Comments below **60 %** are shown in a separate **"⚠️ Verify These"** section with
a `verify this` label, implementing production-grade epistemic humility.

---

## Project Structure

```
.
├── app.py                  # Streamlit dashboard
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── .streamlit/
│   └── config.toml         # dark theme config
└── agent/
    ├── __init__.py
    ├── ingestion.py        # repo cloning (GitPython)
    ├── parser.py           # AST parsing → CodeChunk objects
    ├── reviewer.py         # Gemini API + JSON parsing
    └── pipeline.py         # orchestrator
```

---

## Deployment (Streamlit Cloud)

1. Push this repo to GitHub (make it public)
2. Go to https://share.streamlit.io → **New app**
3. Select your repo, branch `main`, entry point `app.py`
4. Under **Advanced settings → Secrets**, add:
   ```
   GEMINI_API_KEY = "your-key-here"
   ```
5. Deploy — done!

---

## Known Limitations

- **Python only**: The AST parser currently supports Python files only. JS/Go support
  would require `tree-sitter` bindings.
- **Public repos only**: Private repos require a GitHub PAT in `.env`.
- **Free-tier rate limits**: Gemini 1.5 Flash allows ~15 req/min on the free tier.
  The pipeline adds a 1.5 s delay between batches. Large repos (> 80 files) may be
  capped — the agent analyzes the first 80 Python files.
- **No cross-file analysis**: Each chunk is reviewed in isolation. Issues that span
  multiple files (e.g. incorrect interface usage) may be missed.
- **Confidence is model self-reported**: The scores are generated by Gemini itself and
  should be treated as indicative, not ground truth.

---

## What I'd Build Next

- **JavaScript / TypeScript support** via `tree-sitter-javascript`
- **GitHub PR integration** — post inline comments via the GitHub API (`PyGithub`)
- **Incremental analysis** — only re-review files changed since last run (using git diff)
- **Vector store caching** — store chunk embeddings to avoid re-reviewing unchanged code
- **Multi-model consensus** — run the same chunk through two models and only surface
  comments both agree on, to reduce false positives

---

## Academic Integrity

AI tools (Gemini, GitHub Copilot) were used to assist with individual code snippets.
All architecture decisions, prompt design, and integration logic were authored by the
student. All code can be explained during a viva/demo.

---

*CipherSchools Assignment — AI/ML Domain | Built with ❤️ using Gemini + Streamlit*
