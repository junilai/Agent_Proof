"""The LangGraph edition of the case-study agent, as LangGraph Studio shows it.

VARIANT picks the mutation (baseline by default). Compiled without a checkpointer:
the development server adds its own.
"""

import os

from casestudy.editions.langgraph import builder

graph = builder(os.environ.get("VARIANT", "baseline")).compile()
