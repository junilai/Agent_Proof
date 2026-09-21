import importlib

import pytest

import agentproof


def test_package_exposes_version():
    assert agentproof.__version__ == "0.1.0"


@pytest.mark.parametrize("package", ["agentproof", "casestudy", "casestudy.domain", "experiments"])
def test_project_packages_are_importable_and_documented(package):
    assert importlib.import_module(package).__doc__
