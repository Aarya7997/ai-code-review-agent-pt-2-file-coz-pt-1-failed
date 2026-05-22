"""
agent/pipeline.py
──────────────────
Orchestrates the full agent loop:
  1. Ingest   — clone the GitHub repo
  2. Parse    — extract code chunks via AST
  3. Review   — send chunks to Gemini, get structured comments
  4. Return   — flat list of comments + summary metadata
"""

from pathlib import Path
from typing import Callable, Optional

from .ingestion import clone_repository, list_python_files, get_repo_metadata
from .parser    import parse_repository
from .reviewer  import review_chunks


# ── Pipeline steps ─────────────────────────────────────────────────────────

TOTAL_STEPS = 10   # granularity for the progress bar


def run_pipeline(
    repo_url: str,
    api_key: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> tuple[list[dict], dict]:
    """
    Run the complete code review pipeline.

    Parameters
    ----------
    repo_url : str
        Public GitHub repository URL.
    api_key : str, optional
        Gemini API key (falls back to env var GEMINI_API_KEY).
    progress_callback : callable(step, total_steps, message), optional
        Called at key milestones to update a progress bar.

    Returns
    -------
    (comments, meta)
        comments – list of review comment dicts
        meta     – summary dict for the dashboard
    """
    def _progress(step: int, msg: str):
        if progress_callback:
            progress_callback(step, TOTAL_STEPS, msg)

    # ── Step 1: Clone ─────────────────────────────────────────────────────────
    _progress(1, f"🔗 Cloning repository: {repo_url}")
    repo_root: Path = clone_repository(repo_url)

    repo_meta = get_repo_metadata(repo_root)

    # ── Step 2: Discover Python files ─────────────────────────────────────────
    _progress(2, "📂 Discovering Python files…")
    py_files = list_python_files(repo_root, max_files=10)

    if not py_files:
        raise RuntimeError(
            "No Python (.py) files found in this repository. "
            "This agent currently supports Python codebases."
        )

    # ── Step 3–4: Parse all files ─────────────────────────────────────────────
    _progress(3, f"🌳 Parsing {len(py_files)} Python files with AST…")
    chunks, parse_stats = parse_repository(py_files, repo_root, max_chunks=120)

    _progress(4, f"✅ Extracted {len(chunks)} code chunks — ready for review.")

    if not chunks:
        raise RuntimeError(
            "No parseable code chunks found. "
            "All files may have syntax errors or be empty."
        )

    # ── Steps 5–9: LLM review (batched, progress reported per batch) ──────────
    review_step_start = 5
    review_step_end   = 9

    def review_progress(batch_idx: int, total_batches: int, msg: str):
        # Map batch progress into steps 5–9
        frac = batch_idx / max(total_batches, 1)
        step = review_step_start + int(frac * (review_step_end - review_step_start))
        _progress(step, f"🧠 {msg}")

    comments = review_chunks(
        chunks,
        api_key=api_key,
        batch_size=3,
        delay_between_batches=1.5,
        progress_callback=review_progress,
    )

    # ── Step 10: Finalise ─────────────────────────────────────────────────────
    _progress(TOTAL_STEPS, "🎉 Review complete — building results…")

    meta = {
        **parse_stats,
        **repo_meta,
        "repo_url":       repo_url,
        "total_comments": len(comments),
        "py_files_found": len(py_files),
        "chunks_reviewed": len(chunks),
        "parse_error_count": parse_stats.get("files_with_errors", 0),
    }

    # Sort by severity priority then confidence desc
    _severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    comments.sort(
        key=lambda c: (
            _severity_order.get(c.get("severity", "info"), 5),
            -c.get("confidence", 0),
        )
    )

    return comments, meta
