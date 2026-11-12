"""The smolagents edition of the case-study agent, in smolagents' own Gradio UI.

VARIANT picks the mutation (baseline by default). The UI is local only: bound to
127.0.0.1, never shared through a public Gradio link, and with Gradio analytics
and litellm's cost map download turned off before either library is imported.
One agent serves the whole session: restart the script to start a new conversation.
"""

import os

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

HOST = "127.0.0.1"
PORT = 7860
NAME = "andina_tech"


def build_ui(variant: str | None = None):
    from smolagents import GradioUI

    from casestudy.editions.smolagents import builder

    agent = builder(variant or os.environ.get("VARIANT", "baseline"))
    agent.name = NAME
    return GradioUI(agent)


def main() -> None:
    build_ui().launch(share=False, server_name=HOST, server_port=PORT)


if __name__ == "__main__":
    main()
