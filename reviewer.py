"""
agent/reviewer.py
──────────────────
Sends code chunks to Groq (OpenAI-compatible API) and parses structured
JSON review comments.

Each review comment has:
  - severity     : "critical" | "high" | "medium" | "low" | "info"
  - category     : "bug" | "security" | "performance" | "style" | "maintainability" | "logic"
  - title        : short one-line summary
  - comment      : detailed explanation
  - suggestion   : concrete fix suggestion
  - confidence   : 0–100 integer (self-rated by the model)
"""

import json
import os
import re
import time
from typing import Optional

from groq import Groq

from .parser import CodeChunk


# ── Groq setup ────────────────────────────────────────────────────────────────
# Free, fast models. llama-3.3-70b is the strongest free option for code review.
_MODEL_NAME = "llama-3.3-70b-versatile"
_TEMPERATURE = 0.2          # low → consistent structured output
_MAX_TOKENS  = 1500

_VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
_VALID_CATEGORIES = {"bug", "security", "performance", "style", "maintainability", "logic"}


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert code reviewer with deep knowledge of Python best
practices, security vulnerabilities, performance patterns, and clean code principles.

Your task is to analyze the provided code chunk and produce a JSON array of review
comments.  Follow these rules exactly:

RULES:
1. Return ONLY a valid JSON array — no markdown fences, no preamble, no trailing text.
2. Each element must have these fields (all required):
   {
     "severity":   "critical" | "high" | "medium" | "low" | "info",
     "category":   "bug" | "security" | "performance" | "style" | "maintainability" | "logic",
     "title":      "<one concise sentence, max 80 chars>",
     "comment":    "<detailed explanation, 1-4 sentences>",
     "suggestion": "<concrete, actionable fix>",
     "confidence": <integer 0-100>,
     "file":       "<the file path from the '# File:' header>",
     "location":   "<line range, e.g. L12-34>"
   }
3. Confidence scoring rules:
   - 90-100: You are certain this is a real issue with clear evidence in the code.
   - 70-89:  Likely an issue, but context outside this chunk might change the verdict.
   - 50-69:  Possible issue — depends on wider codebase context you do not have.
   - 0-49:   Speculative — flag it but it may be intentional or context-dependent.
4. Do NOT invent issues. If the code is clean, return [].
5. Do NOT hallucinate function signatures or variable names not present in the code.
6. Limit output to a maximum of 5 comments per chunk. Prioritise by severity.
7. Focus on real engineering problems: bugs, security holes, logic errors,
   performance anti-patterns, dangerous patterns — not trivial style nits.

Return [] if there are no meaningful issues."""


# ── Public API ────────────────────────────────────────────────────────────────

def review_chunks(
    chunks: list[CodeChunk],
    api_key: Optional[str] = None,
    batch_size: int = 3,
    delay_between_batches: float = 1.2,
    progress_callback=None,
) -> list[dict]:
    """
    Review a list of CodeChunks and return a flat list of comment dicts.

    Parameters
    ----------
    chunks : list[CodeChunk]
    api_key : str, optional
        Groq API key. Falls back to GROQ_API_KEY env var.
    batch_size : int
        Number of chunks to group into a single API call.
    delay_between_batches : float
        Seconds to sleep between calls (respect free-tier rate limits).
    progress_callback : callable(current, total, msg), optional
        Called after each batch to report progress.

    Returns
    -------
    list[dict]
        Each dict is a review comment with file/location context added.
    """
    client = _make_client(api_key)

    all_comments: list[dict] = []
    batches = _make_batches(chunks, batch_size)

    for i, batch in enumerate(batches):
        if progress_callback:
            progress_callback(
                i + 1,
                len(batches),
                f"Reviewing batch {i+1}/{len(batches)} ({len(batch)} chunks)…",
            )

        prompt = _build_batch_prompt(batch)

        try:
            raw_comments = _call_groq(client, prompt)
        except Exception as exc:
            raw_comments = []
            print(f"[reviewer] Batch {i+1} error: {exc}")

        for comment in raw_comments:
            _enrich_comment(comment, batch)
            all_comments.append(comment)

        if i < len(batches) - 1:
            time.sleep(delay_between_batches)

    return all_comments


# ── Groq helpers ──────────────────────────────────────────────────────────────

def _make_client(api_key: Optional[str]) -> Groq:
    key = api_key or os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError(
            "No Groq API key found. Set GROQ_API_KEY in your .env file, "
            "paste it in the sidebar, or pass api_key= to review_chunks(). "
            "Get a free key at https://console.groq.com/keys"
        )
    return Groq(api_key=key)


def _make_batches(chunks: list[CodeChunk], size: int) -> list[list[CodeChunk]]:
    return [chunks[i : i + size] for i in range(0, len(chunks), size)]


def _build_batch_prompt(batch: list[CodeChunk]) -> str:
    parts = []
    for idx, chunk in enumerate(batch, 1):
        parts.append(f"--- CHUNK {idx} ---")
        parts.append(chunk.to_prompt_block())
    parts.append("")
    parts.append(
        "Review ALL chunks above and return a single JSON array of comments. "
        "Each comment MUST include a 'file' field matching the '# File:' header "
        "of the chunk it refers to, and a 'location' field (e.g. 'L12-34'). "
        "Return [] if no issues found."
    )
    return "\n".join(parts)


def _call_groq(client: Groq, prompt: str) -> list[dict]:
    """Call Groq chat completion and return parsed JSON list of comments."""
    response = client.chat.completions.create(
        model=_MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
    )
    raw_text = response.choices[0].message.content.strip()
    return _parse_json_response(raw_text)


def _parse_json_response(text: str) -> list[dict]:
    """Robustly parse a JSON array from the model's response."""
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    return [_validate_comment(c) for c in data if isinstance(c, dict) and _is_valid(c)]


def _is_valid(comment: dict) -> bool:
    required = {"severity", "category", "title", "comment", "suggestion", "confidence"}
    if not required.issubset(comment.keys()):
        return False
    if str(comment["severity"]).lower() not in _VALID_SEVERITIES:
        return False
    if str(comment["category"]).lower() not in _VALID_CATEGORIES:
        return False
    if not isinstance(comment["confidence"], (int, float)):
        return False
    return True


def _validate_comment(comment: dict) -> dict:
    comment["severity"]   = str(comment["severity"]).lower()
    comment["category"]   = str(comment["category"]).lower()
    comment["confidence"] = max(0, min(100, int(comment["confidence"])))
    comment.setdefault("file", "unknown")
    comment.setdefault("location", "")
    return comment


def _enrich_comment(comment: dict, batch: list[CodeChunk]) -> None:
    if comment.get("file", "unknown") == "unknown" and batch:
        comment["file"]     = batch[0].file_path
        comment["location"] = batch[0].location
        return

    file_val = comment.get("file", "")
    for chunk in batch:
        if chunk.file_path.endswith(file_val) or file_val.endswith(chunk.file_path):
            comment["file"] = chunk.file_path
            if not comment.get("location"):
                comment["location"] = chunk.location
            return
