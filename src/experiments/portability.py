"""Incorporation cost of each agent framework (spec F4, §8; counting rule D-014).

    python -m experiments.portability [--csv]

Prints, for the Claude Agent SDK (the reference) and each framework added in F4,
the lines of code of its adapter, its edition and its tests, the files of the
core it had to modify and the size of its local interface under ``studio/``.

A line of code is a logical line of Python: one statement, however many
physical lines the formatter splits it into. Blank lines, comments and
docstrings (the first statement of a module, class or function, when it is a
string) do not count. Any other string counts, whatever its length.
"""

from __future__ import annotations

import ast
import io
import subprocess
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

NON_CODE = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}
DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


Span = tuple[tuple[int, int], tuple[int, int]]


def _docstrings(source: str) -> list[Span]:
    """Start and end (line, column) of every module, class or function docstring."""
    spans: list[Span] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, DOCSTRING_OWNERS) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            end = (first.end_lineno or first.lineno, first.end_col_offset or 0)
            spans.append(((first.lineno, first.col_offset), end))
    return spans


def _code_tokens(source: str) -> Iterator[tokenize.TokenInfo]:
    """Tokens of ``source`` that are code: no layout, comments or docstrings."""
    docstrings = _docstrings(source)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NEWLINE:
            yield token
        elif token.type not in NON_CODE and not any(
            start <= token.start and token.end <= end for start, end in docstrings
        ):
            yield token


def logical_lines(source: str) -> int:
    """Statements of ``source`` that are not docstrings."""
    count, has_code = 0, False
    for token in _code_tokens(source):
        if token.type == tokenize.NEWLINE:
            count += has_code
            has_code = False
        else:
            has_code = True
    return count


def physical_lines(source: str) -> int:
    """Physical lines of ``source`` with code on them, outside docstrings."""
    lines: set[int] = set()
    for token in _code_tokens(source):
        if token.type != tokenize.NEWLINE:
            lines.update(range(token.start[0], token.end[0] + 1))
    return len(lines)


CORE = "src/agentproof/"
OUTSIDE_CORE = "src/agentproof/adapters/"


class HistoryUnavailable(Exception):
    """The git history needed to count the core files is not there."""


@dataclass(frozen=True)
class PullRequest:
    """A framework merged in its own pull request: everything between its base and its tip."""

    base: str
    tip: str


@dataclass(frozen=True)
class Mentions:
    """A framework whose commits, after ``since``, mention it in their message."""

    since: str
    word: str


def _git(repo: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise HistoryUnavailable(f"git no pudo leer {repo}: {error}") from error
    return done.stdout.strip()


def _require(repo: Path, *commits: str) -> None:
    if _git(repo, "rev-parse", "--is-shallow-repository") == "true":
        raise HistoryUnavailable(
            "clon superficial: falta la historia de los frameworks (git fetch --unshallow)"
        )
    for commit in commits:
        try:
            _git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
        except HistoryUnavailable:
            raise HistoryUnavailable(f"el commit {commit} no está en la historia") from None


def _changed_files(repo: Path, history: PullRequest | Mentions) -> list[str]:
    if isinstance(history, PullRequest):
        _require(repo, history.base, history.tip)
        return _git(repo, "diff", "--name-only", history.base, history.tip).splitlines()
    _require(repo, history.since)
    span = f"{history.since}..HEAD"
    grep = ["--regexp-ignore-case", f"--grep={history.word}"]
    if not _git(repo, "log", "--format=%H", *grep, span):
        raise HistoryUnavailable(
            f"ningún commit posterior a {history.since} menciona {history.word}"
        )
    return _git(repo, "log", "--name-only", "--format=", *grep, span).splitlines()


def core_files(repo: Path, history: PullRequest | Mentions) -> list[str]:
    """Files of the core (``src/agentproof`` outside ``adapters/``) a framework modified."""
    files = _changed_files(repo, history)
    return sorted({f for f in files if f.startswith(CORE) and not f.startswith(OUTSIDE_CORE)})
