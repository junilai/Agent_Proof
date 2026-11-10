"""Every edition of the case-study agent applies the same six mutations (§5.8)."""

import importlib

import pytest

from casestudy.domain.mutations import MUTATIONS

EDITIONS = {
    "casestudy.editions.claude_sdk": "build_options",
    "casestudy.editions.langgraph": "builder",
}


@pytest.mark.parametrize(("edition", "build"), EDITIONS.items())
def test_every_edition_builds_every_mutation(edition, build):
    module = importlib.import_module(edition)
    assert set(MUTATIONS) <= set(module.VARIANTS)
    for variant in MUTATIONS:
        assert getattr(module, build)(variant) is not None
