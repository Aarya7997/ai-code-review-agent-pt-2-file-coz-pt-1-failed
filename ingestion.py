"""
agent/ingestion.py
──────────────────
Clones (or reuses) a GitHub repository into a local temp directory.
Uses GitPython for cloning and basic validation.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import git  # gitpython


# ── Constants ─────────────────────────────────────────────────────────────────
CLONE_BASE_DIR = Path(tempfile.gettempdir()) / "ai_code_review_repos"
GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?$"
)
MAX_REPO_SIZE_MB = 150  # refuse repos larger than this


# ── Public API ────────────────────────────────────────────────────────────────

def clone_repository(repo_url: str, force_reclone: bool = False) -> Path:
    """
    Clone *repo_url* into a deterministic local path and return that path.

    Parameters
    ----------
    repo_url : str
        A public GitHub HTTPS URL, e.g. "https://github.com/user/repo"
    force_reclone : bool
        If True, delete any cached clone and re-clone from scratch.

    Returns
    -------
    Path
        Absolute path to the root of the cloned repository.

    Raises
    ------
    ValueError
        If the URL is not a recognised GitHub HTTPS URL.
    RuntimeError
        If cloning fails or the repo exceeds the size limit.
    """
    repo_url = _normalise_url(repo_url)
    _validate_url(repo_url)

    clone_dir = _clone_path(repo_url)
    CLONE_BASE_DIR.mkdir(parents=True, exist_ok=True)

    if clone_dir.exists():
        if force_reclone:
            shutil.rmtree(clone_dir)
        else:
            # Verify it's a valid git repo; if broken, re-clone
            try:
                git.Repo(clone_dir).git.status()
                return clone_dir
            except Exception:
                shutil.rmtree(clone_dir)

    try:
        git.Repo.clone_from(
            repo_url,
            str(clone_dir),
            depth=1,           # shallow clone — faster, smaller
            single_branch=True,
        )
    except git.exc.GitCommandError as exc:
        raise RuntimeError(
            f"Failed to clone '{repo_url}'. "
            "Make sure the repository is public and the URL is correct.\n"
            f"Git error: {exc}"
        ) from exc

    _check_size(clone_dir)
    return clone_dir


def list_python_files(repo_root: Path, max_files: int = 80) -> list[Path]:
    """
    Return up to *max_files* Python (.py) source files from *repo_root*,
    excluding common non-project directories.
    """
    EXCLUDED_DIRS = {
        ".git", "__pycache__", ".venv", "venv", "env", ".env",
        "node_modules", "dist", "build", ".tox", ".mypy_cache",
        ".pytest_cache", "site-packages", "migrations",
    }

    py_files: list[Path] = []
    for path in sorted(repo_root.rglob("*.py")):
        # Skip if any parent dir is in the exclusion list
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        # Skip auto-generated files
        if path.name.startswith("_pb2") or path.stem.endswith("_generated"):
            continue
        py_files.append(path)
        if len(py_files) >= max_files:
            break

    return py_files


def get_repo_metadata(repo_root: Path) -> dict:
    """Return basic metadata about the cloned repository."""
    try:
        repo = git.Repo(repo_root)
        return {
            "remote_url": next(iter(repo.remotes[0].urls), "unknown") if repo.remotes else "unknown",
            "branch": repo.active_branch.name,
            "last_commit": repo.head.commit.hexsha[:7],
            "commit_message": repo.head.commit.message.strip()[:100],
        }
    except Exception:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url


def _validate_url(url: str) -> None:
    if not GITHUB_URL_PATTERN.match(url):
        raise ValueError(
            f"Invalid GitHub URL: '{url}'\n"
            "Expected format: https://github.com/<owner>/<repo>"
        )


def _clone_path(repo_url: str) -> Path:
    """Convert a repo URL into a deterministic local directory name."""
    # e.g. https://github.com/psf/requests → psf__requests
    slug = repo_url.replace("https://github.com/", "").replace("/", "__")
    return CLONE_BASE_DIR / slug


def _check_size(clone_dir: Path) -> None:
    total_bytes = sum(
        f.stat().st_size for f in clone_dir.rglob("*") if f.is_file()
    )
    size_mb = total_bytes / (1024 ** 2)
    if size_mb > MAX_REPO_SIZE_MB:
        shutil.rmtree(clone_dir)
        raise RuntimeError(
            f"Repository is {size_mb:.1f} MB, which exceeds the "
            f"{MAX_REPO_SIZE_MB} MB limit. Please use a smaller repo."
        )
