import os

# litellm downloads its model cost map from GitHub when first imported, unless
# told to use the bundled copy; tests never reach the network.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
