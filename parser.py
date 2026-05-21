"""
agent/parser.py
───────────────
Extracts structured information from Python source files using the
built-in `ast` module.  Each extracted unit (function, class, module-level
code) becomes a *chunk* that is later sent to the LLM for review.
"""

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class CodeChunk:
    """A self-contained unit of code ready for LLM review."""
    file_path: str          # relative path from repo root
    chunk_type: str         # "function" | "class" | "module"
    name: str               # qualified name, e.g. "MyClass.my_method"
    source: str             # the raw source text for this chunk
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    decorators: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)   # file-level imports

    @property
    def location(self) -> str:
        return f"L{self.start_line}–{self.end_line}"

    def to_prompt_block(self) -> str:
        """Format the chunk for inclusion in an LLM prompt."""
        header = (
            f"# File: {self.file_path}  ({self.location})\n"
            f"# Type: {self.chunk_type}  |  Name: {self.name}\n"
        )
        if self.imports:
            header += "# Imports in file: " + ", ".join(self.imports[:10]) + "\n"
        return header + "\n" + self.source


@dataclass
class ParseResult:
    """All chunks extracted from a single file."""
    file_path: str
    chunks: list[CodeChunk]
    parse_error: Optional[str] = None
    total_lines: int = 0
    num_functions: int = 0
    num_classes: int = 0


# ── Public API ────────────────────────────────────────────────────────────────

def parse_file(file_path: Path, repo_root: Path) -> ParseResult:
    """
    Parse a single Python file and return its extracted chunks.

    Parameters
    ----------
    file_path : Path
        Absolute path to the .py file.
    repo_root : Path
        Root of the cloned repository (used to compute relative paths).
    """
    relative = str(file_path.relative_to(repo_root))

    try:
        source_text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ParseResult(file_path=relative, chunks=[], parse_error=str(exc))

    try:
        tree = ast.parse(source_text, filename=str(file_path))
    except SyntaxError as exc:
        return ParseResult(
            file_path=relative,
            chunks=[],
            parse_error=f"SyntaxError at line {exc.lineno}: {exc.msg}",
        )

    source_lines = source_text.splitlines()
    imports = _extract_imports(tree)
    chunks: list[CodeChunk] = []

    # ── Top-level functions ───────────────────────────────────────────────────
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Only grab top-level and first-level class methods
            chunk = _function_chunk(node, source_lines, relative, imports)
            if chunk:
                chunks.append(chunk)

    # ── Top-level classes (whole class body as one chunk if small enough) ─────
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            chunk = _class_chunk(node, source_lines, relative, imports)
            if chunk:
                chunks.append(chunk)

    # ── Fallback: if no functions/classes, send the whole file ────────────────
    if not chunks:
        chunks.append(
            CodeChunk(
                file_path=relative,
                chunk_type="module",
                name="<module>",
                source=_cap_source(source_text, max_lines=120),
                start_line=1,
                end_line=len(source_lines),
                imports=imports,
            )
        )

    num_functions = sum(1 for c in chunks if c.chunk_type == "function")
    num_classes   = sum(1 for c in chunks if c.chunk_type == "class")

    return ParseResult(
        file_path=relative,
        chunks=chunks,
        total_lines=len(source_lines),
        num_functions=num_functions,
        num_classes=num_classes,
    )


def parse_repository(
    py_files: list[Path],
    repo_root: Path,
    max_chunks: int = 120,
) -> tuple[list[CodeChunk], dict]:
    """
    Parse all Python files and return a flat list of chunks + summary stats.

    Parameters
    ----------
    py_files : list[Path]
        Python files to parse (from ingestion.list_python_files).
    repo_root : Path
        Repository root directory.
    max_chunks : int
        Hard cap to avoid overwhelming the LLM quota.

    Returns
    -------
    (chunks, stats)
        chunks – flat list of CodeChunk objects
        stats  – dict with files_parsed, functions_found, classes_found, errors
    """
    all_chunks: list[CodeChunk] = []
    stats = {
        "files_parsed": 0,
        "files_with_errors": 0,
        "functions_found": 0,
        "classes_found": 0,
        "total_lines": 0,
        "parse_errors": [],
    }

    for fp in py_files:
        if len(all_chunks) >= max_chunks:
            break
        result = parse_file(fp, repo_root)
        if result.parse_error:
            stats["files_with_errors"] += 1
            stats["parse_errors"].append(
                {"file": result.file_path, "error": result.parse_error}
            )
            continue
        stats["files_parsed"] += 1
        stats["functions_found"] += result.num_functions
        stats["classes_found"]   += result.num_classes
        stats["total_lines"]     += result.total_lines
        all_chunks.extend(result.chunks)

    # Trim to cap
    all_chunks = all_chunks[:max_chunks]
    return all_chunks, stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_imports(tree: ast.Module) -> list[str]:
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
    return imports[:20]


def _get_source_segment(source_lines: list[str], start: int, end: int) -> str:
    """Extract lines [start, end] (1-indexed, inclusive) from source_lines."""
    segment = "\n".join(source_lines[start - 1 : end])
    return textwrap.dedent(segment)


def _function_chunk(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: list[str],
    relative: str,
    imports: list[str],
) -> Optional[CodeChunk]:
    """Build a CodeChunk from a function/method node."""
    start = node.lineno
    end   = node.end_lineno or start
    if end - start > 200:          # skip giant generated functions
        return None
    source = _get_source_segment(source_lines, start, end)
    docstring = ast.get_docstring(node)
    decorators = [ast.unparse(d) for d in node.decorator_list]

    return CodeChunk(
        file_path=relative,
        chunk_type="function",
        name=node.name,
        source=_cap_source(source, max_lines=100),
        start_line=start,
        end_line=end,
        docstring=docstring,
        decorators=decorators,
        imports=imports,
    )


def _class_chunk(
    node: ast.ClassDef,
    source_lines: list[str],
    relative: str,
    imports: list[str],
) -> Optional[CodeChunk]:
    """Build a CodeChunk for an entire class (capped at 150 lines)."""
    start = node.lineno
    end   = node.end_lineno or start
    if end - start > 250:
        return None  # too large — individual methods already extracted
    source = _get_source_segment(source_lines, start, end)
    docstring = ast.get_docstring(node)

    return CodeChunk(
        file_path=relative,
        chunk_type="class",
        name=node.name,
        source=_cap_source(source, max_lines=150),
        start_line=start,
        end_line=end,
        docstring=docstring,
        imports=imports,
    )


def _cap_source(source: str, max_lines: int) -> str:
    """Truncate source to *max_lines* lines, appending a note if cut."""
    lines = source.splitlines()
    if len(lines) <= max_lines:
        return source
    truncated = "\n".join(lines[:max_lines])
    return truncated + f"\n# … ({len(lines) - max_lines} more lines truncated)"
