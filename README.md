# AI Code Review Agent

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
### 4. Run the app

```bash
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`.

---





*CipherSchools Assignment — AI/ML Domain | Built with ❤️ using Gemini + Streamlit*
