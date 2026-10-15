"""Every edition of the case-study agent applies the same six mutations (§5.8)."""

import importlib

import pytest

from casestudy.domain.mutations import MUTATIONS

EDITIONS = ["casestudy.editions.claude_sdk"]


@pytest.mark.parametrize("edition", EDITIONS)
def test_every_edition_builds_every_mutation(edition):
    module = importlib.import_module(edition)
    assert set(MUTATIONS) <= set(module.VARIANTS)
    for variant in MUTATIONS:
        assert module.build_options(variant) is not None
