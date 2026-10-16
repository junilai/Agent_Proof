"""Ground truth of the experiment (§5.4).

The oracle decides which scenarios are exposed to each degradation, which outcome
the agent communicated and whether that outcome is a failure. It relies only on
sources fixed before the execution and alien to AgentProof: the knowledge base of
the case study, the situation card and the events of the trace. It never uses the
automatic judge nor the induced scenarios; from a run it reaches the seed through
the scenario identifier, and from the seed the card. What the rules cannot
resolve is not guessed: it goes to manual annotation.
"""
