"""Framework adapters.

Each adapter module exposes ``session_factory(agent, variant) -> SessionFactory``,
where ``agent`` builds the framework-native agent for a variant. These are the
only modules of AgentProof allowed to import an agent framework.
"""
