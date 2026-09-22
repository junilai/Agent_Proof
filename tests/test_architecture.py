"""Architectural invariants of the master plan (docs/specs/2026-09-21-plan-maestro.md, §1).

The core (``agentproof`` outside ``adapters/``) must stay independent of any
agent framework and of the case study and experimental packages. The check
is static: it parses every core module and inspects its imports, including
imports nested inside functions.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
CORE = SRC / "agentproof"
CASE_STUDY = SRC / "casestudy"

AGENT_FRAMEWORKS = {
    "claude_agent_sdk",
    "crewai",
    "langchain",
    "langchain_anthropic",
    "langchain_core",
    "langgraph",
    "litellm",
    "smolagents",
}
OFF_LIMITS_PROJECT_PACKAGES = {"casestudy", "experiments"}


def imported_modules(source: str) -> set[str]:
    """Full dotted name of every absolute import in ``source``."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def imported_top_level_modules(source: str) -> set[str]:
    """Top-level names of every absolute import in ``source``."""
    return {module.split(".")[0] for module in imported_modules(source)}


def core_modules() -> list[Path]:
    return [p for p in CORE.rglob("*.py") if "adapters" not in p.relative_to(CORE).parts]


def forbidden_imports(forbidden: set[str]) -> dict[str, set[str]]:
    found = {
        str(path.relative_to(SRC)): imported_top_level_modules(path.read_text()) & forbidden
        for path in core_modules()
    }
    return {module: names for module, names in found.items() if names}


def test_detects_nested_absolute_imports_and_ignores_relative_ones():
    source = (
        "import langgraph.graph\n"
        "from crewai import Agent\n"
        "from . import schema\n"
        "def build():\n"
        "    import smolagents\n"
    )
    assert imported_top_level_modules(source) == {"langgraph", "crewai", "smolagents"}


def test_core_is_not_empty():
    assert core_modules(), f"no core modules found under {CORE}"


def test_core_does_not_import_agent_frameworks():
    assert forbidden_imports(AGENT_FRAMEWORKS) == {}


def test_core_does_not_import_case_study_or_experiments():
    assert forbidden_imports(OFF_LIMITS_PROJECT_PACKAGES) == {}


def test_detects_full_module_names():
    source = (
        "from agentproof.models import X\nimport agentproof.store\nfrom agentproof import schema\n"
    )
    assert imported_modules(source) == {"agentproof.models", "agentproof.store", "agentproof"}


def test_case_study_imports_nothing_from_agentproof_but_models():
    offending = {}
    for path in CASE_STUDY.rglob("*.py"):
        used = {m for m in imported_modules(path.read_text()) if m.split(".")[0] == "agentproof"}
        if used - {"agentproof.models"}:
            offending[str(path.relative_to(SRC))] = used - {"agentproof.models"}
    assert offending == {}


def test_case_study_domain_imports_no_agent_framework():
    found = {
        str(p.relative_to(SRC)): imported_top_level_modules(p.read_text()) & AGENT_FRAMEWORKS
        for p in (CASE_STUDY / "domain").rglob("*.py")
    }
    assert {k: v for k, v in found.items() if v} == {}
