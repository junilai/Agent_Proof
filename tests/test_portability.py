"""Incorporation cost of each framework (spec F4, §8; counting rule D-014)."""

import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from experiments.portability import (
    FRAMEWORKS,
    REPO,
    HistoryUnavailable,
    Mentions,
    PullRequest,
    core_files,
    logical_lines,
    measure,
    physical_lines,
    studio_lines,
)


def src(text: str) -> str:
    return dedent(text).lstrip("\n")


def test_blank_lines_and_comments_do_not_count():
    source = src(
        """
        # a comment

        x = 1  # an inline comment does not remove the code

            # an indented comment
        """
    )
    assert logical_lines(source) == 1
    assert physical_lines(source) == 1


def test_module_class_and_function_docstrings_do_not_count():
    source = src(
        '''
        """Module docstring,
        on two lines."""


        class A:
            """Class docstring."""

            def f(self):
                """Function
                docstring."""
                return 1


        async def g():
            "single-quoted docstring"
            return 2
        '''
    )
    # class A, def f, return 1, async def g, return 2
    assert logical_lines(source) == 5
    assert physical_lines(source) == 5


def test_a_multiline_string_that_is_not_a_docstring_counts():
    source = src(
        '''
        def f():
            x = 1
            """Not a docstring: it is not the first statement."""
            return x


        TEXT = """
        first line

        third line
        """
        '''
    )
    # def, x = 1, the bare string, return, TEXT = ...
    assert logical_lines(source) == 5
    # the string assigned to TEXT spans five physical lines, the blank one included
    assert physical_lines(source) == 4 + 5


def test_a_statement_split_across_lines_is_one_logical_line():
    source = src(
        """
        total = 1 + \\
            2
        call(
            1,  # a comment inside the brackets
            2,
        )
        a = 1; b = 2
        """
    )
    assert logical_lines(source) == 3
    assert physical_lines(source) == 2 + 4 + 1


def test_a_docstring_alone_or_an_empty_source_counts_zero():
    assert logical_lines('"""Only a docstring."""\n') == 0
    assert logical_lines("") == 0
    assert physical_lines("# only a comment\n") == 0


def test_a_source_without_a_final_newline_still_counts_its_last_line():
    assert logical_lines("x = 1\ny = 2") == 2
    assert physical_lines("x = 1\ny = 2") == 2


def test_a_one_line_function_keeps_its_header_but_not_its_docstring():
    source = 'def f(): "docstring"\n\n\ndef g():\n    "docstring"; x = 1\n'
    # def f, def g, x = 1 (the docstring shares its logical line with code)
    assert logical_lines(source) == 2 + 1
    assert physical_lines(source) == 2 + 1


def git(repo, *args):
    command = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    command += ["-c", "commit.gpgsign=false", *args]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, message, *paths):
    for path in paths:
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(file.read_text() + "x = 1\n" if file.exists() else "x = 1\n")
    git(repo, "add", *paths)
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    shas = {
        "base": commit(repo, "inicio", "src/agentproof/core.py", "src/agentproof/store.py"),
        "tip": commit(
            repo,
            "feat: un framework",
            "src/agentproof/adapters/one.py",
            "src/agentproof/core.py",
            "docs/x.md",
        ),
    }
    commit(
        repo, "feat(adapters): SmolAgents", "src/agentproof/adapters/s.py", "src/agentproof/a.py"
    )
    commit(repo, "fix: otra cosa", "src/agentproof/store.py")
    commit(repo, "test: modelo falso de smolagents", "tests/fakes_s.py", "src/agentproof/b.py")
    return repo, shas


def test_a_pull_request_modifies_the_core_files_between_its_base_and_its_tip(history):
    repo, shas = history
    assert core_files(repo, PullRequest(shas["base"], shas["tip"])) == ["src/agentproof/core.py"]


def test_commits_that_mention_a_framework_are_its_own_whatever_the_case(history):
    repo, shas = history
    found = core_files(repo, Mentions(since=shas["tip"], word="smolagents"))
    assert found == ["src/agentproof/a.py", "src/agentproof/b.py"]


def test_no_commit_mentioning_the_framework_is_not_reported_as_zero_files(history):
    repo, shas = history
    with pytest.raises(HistoryUnavailable, match="crewai"):
        core_files(repo, Mentions(since=shas["tip"], word="crewai"))


def test_a_commit_missing_from_the_history_is_reported(history):
    repo, _ = history
    with pytest.raises(HistoryUnavailable, match="no está en la historia"):
        core_files(repo, PullRequest("0" * 40, "1" * 40))


def test_a_shallow_clone_is_reported_instead_of_counted(history, tmp_path):
    repo, shas = history
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow))
    with pytest.raises(HistoryUnavailable, match="clon superficial"):
        core_files(shallow, PullRequest(shas["base"], shas["tip"]))


def test_a_folder_that_is_not_a_repository_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    with pytest.raises(HistoryUnavailable, match="git"):
        core_files(tmp_path, PullRequest("a", "b"))


# A test file whose name carries one of these words belongs to that framework.
KEYWORDS = {
    "Claude Agent SDK": ("claude_sdk",),
    "LangGraph": ("langgraph", "langchain"),
    "CrewAI": ("crewai",),
    "smolagents": ("smolagents",),
}


def declared_files(framework):
    return [framework.adapter, framework.edition, *framework.tests, *framework.live_tests]


def test_the_four_frameworks_are_declared_in_order_with_files_that_exist():
    assert [f.name for f in FRAMEWORKS] == list(KEYWORDS)
    for framework in FRAMEWORKS:
        for path in declared_files(framework):
            assert (REPO / path).is_file(), path
        assert framework.studio is None or (REPO / framework.studio).is_dir()


def test_no_test_file_named_after_a_framework_is_left_out_or_counted_twice():
    owners: dict[str, str] = {}
    for framework in FRAMEWORKS:
        for path in [*framework.tests, *framework.live_tests]:
            assert path not in owners, path
            owners[path] = framework.name
    for path in sorted((REPO / "tests").glob("*.py")):
        relative = str(path.relative_to(REPO))
        for name, words in KEYWORDS.items():
            if any(word in path.stem for word in words):
                assert owners.get(relative) == name, relative


def test_studio_counts_python_and_configuration_but_not_the_readme(tmp_path):
    (tmp_path / "app.py").write_text('"""Docstring."""\n\nimport x\n\nx.run()\n')
    (tmp_path / "config.json").write_text('{\n  "a": 1\n\n}\n')
    (tmp_path / "README.md").write_text("# Uso\n\nuv run ...\n")
    assert studio_lines(tmp_path) == 2 + 3


def test_measuring_this_repository_gives_one_row_per_framework():
    rows = measure()
    assert [row.name for row in rows] == [f.name for f in FRAMEWORKS]
    assert all(row.adapter > 0 and row.edition > 0 and row.tests > 0 for row in rows)


def test_the_repository_root_is_the_one_holding_the_package():
    assert REPO == Path(__file__).resolve().parents[1]
