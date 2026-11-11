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


REPO = Path(__file__).resolve().parents[2]
# PR #29 (merge commit 012a7a8): its first parent is the base, its second the tip.
LANGGRAPH_PR = PullRequest(
    base="25aaf0875809436984538a9ece541cc3f754b034",
    tip="6fca5127dba89ac5f9ac909a8857e2aba22fbc30",
)
AFTER_LANGGRAPH = "012a7a80c7d617540a86433731c4797f46719954"


@dataclass(frozen=True)
class Framework:
    """What belongs to one framework. ``history`` is None for the reference."""

    name: str
    adapter: str
    edition: str
    tests: tuple[str, ...]
    live_tests: tuple[str, ...]
    studio: str | None
    history: PullRequest | Mentions | None


# Tests: the framework's own test files, its fake model and the tests of that fake
# and of its studio. The core's fakes (tests/fakes.py) and the test every edition
# shares (tests/test_editions_mutations.py) belong to no framework. Live tests call
# the paid API and never run in CI, so they are counted apart.
FRAMEWORKS = (
    Framework(
        name="Claude Agent SDK",
        adapter="src/agentproof/adapters/claude_sdk.py",
        edition="src/casestudy/editions/claude_sdk.py",
        tests=("tests/test_adapter_claude_sdk.py", "tests/test_edition_claude_sdk.py"),
        live_tests=("tests/test_live_agent.py", "tests/test_live_mutations.py"),
        studio=None,
        history=None,
    ),
    Framework(
        name="LangGraph",
        adapter="src/agentproof/adapters/langgraph.py",
        edition="src/casestudy/editions/langgraph.py",
        tests=(
            "tests/test_adapter_langgraph.py",
            "tests/test_edition_langgraph.py",
            "tests/fakes_langchain.py",
            "tests/test_fakes_langchain.py",
        ),
        live_tests=("tests/test_live_langgraph.py",),
        studio="studio/langgraph",
        history=LANGGRAPH_PR,
    ),
    Framework(
        name="CrewAI",
        adapter="src/agentproof/adapters/crewai.py",
        edition="src/casestudy/editions/crewai.py",
        tests=(
            "tests/test_adapter_crewai.py",
            "tests/test_edition_crewai.py",
            "tests/test_edition_crewai_anthropic.py",
            "tests/fakes_crewai.py",
            "tests/test_fakes_crewai.py",
            "tests/test_studio_crewai.py",
        ),
        live_tests=(),
        studio="studio/crewai",
        history=Mentions(since=AFTER_LANGGRAPH, word="crewai"),
    ),
    Framework(
        name="smolagents",
        adapter="src/agentproof/adapters/smolagents.py",
        edition="src/casestudy/editions/smolagents.py",
        tests=(
            "tests/test_adapter_smolagents.py",
            "tests/test_edition_smolagents.py",
            "tests/fakes_smolagents.py",
            "tests/test_fakes_smolagents.py",
        ),
        live_tests=(),
        studio="studio/smolagents",
        history=Mentions(since=AFTER_LANGGRAPH, word="smolagents"),
    ),
)
NOT_APPLICABLE = "—"
UNAVAILABLE = "n/d"


def studio_lines(folder: Path) -> int:
    """Logical lines of the Python files plus non-blank lines of the configuration."""
    total = 0
    for path in sorted(folder.rglob("*")):
        if path.suffix == ".py":
            total += logical_lines(path.read_text())
        elif path.suffix == ".json":
            total += sum(1 for line in path.read_text().splitlines() if line.strip())
    return total


@dataclass(frozen=True)
class Row:
    name: str
    adapter: int
    edition: int
    tests: int
    live_tests: int
    core: list[str] | None
    unavailable: str | None
    studio: int | None


def _lines(repo: Path, paths: tuple[str, ...]) -> int:
    return sum(logical_lines((repo / path).read_text()) for path in paths)


def measure(repo: Path = REPO) -> list[Row]:
    rows = []
    for framework in FRAMEWORKS:
        core, unavailable = None, None
        if framework.history is not None:
            try:
                core = core_files(repo, framework.history)
            except HistoryUnavailable as error:
                unavailable = str(error)
        studio = None if framework.studio is None else studio_lines(repo / framework.studio)
        rows.append(
            Row(
                name=framework.name,
                adapter=_lines(repo, (framework.adapter,)),
                edition=_lines(repo, (framework.edition,)),
                tests=_lines(repo, framework.tests),
                live_tests=_lines(repo, framework.live_tests),
                core=core,
                unavailable=unavailable,
                studio=studio,
            )
        )
    return rows
