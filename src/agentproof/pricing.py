"""Prices of the pinned models, in USD per million tokens (D-007).

Copied from the official pricing page on the date below; the tool's figures are
its own calculation and are reconciled with the billing console. A model that
is not in the table is reported as unpriced, never estimated.
"""

from datetime import date

PRICES_AS_OF = date(2026, 10, 16)
PRICES_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"

PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
"""Model -> (input, output) in USD per million tokens, without caching."""
