"""Adapter convention for tests: the agent builder already returns a session."""


def session_factory(agent, variant):
    return lambda: agent(variant)
