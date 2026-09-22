"""Pinned model identifiers and call settings for every LLM component (§5.6).

Changing a value here changes an experimental condition, so it is a protocol
change, not a tweak. The full configuration is recorded with every trace and
every run. Opus 5 and Sonnet 5 do not accept a fixed temperature; the reasoning
effort is pinned instead. Haiku 4.5 does not accept an effort setting.
"""

from dataclasses import asdict, dataclass

INDUCER_MODEL = "claude-opus-5"
JUDGE_MODEL = "claude-opus-5"
SIM_USER_MODEL = "claude-haiku-4-5-20251001"
TARGET_BASELINE_MODEL = "claude-sonnet-5"
TARGET_DOWNGRADED_MODEL = "claude-haiku-4-5-20251001"


@dataclass(frozen=True)
class CallSettings:
    model: str
    max_tokens: int
    effort: str | None = None


INDUCER = CallSettings(INDUCER_MODEL, max_tokens=16000, effort="high")
JUDGE = CallSettings(JUDGE_MODEL, max_tokens=16000, effort="high")
SIM_USER = CallSettings(SIM_USER_MODEL, max_tokens=1024)


def snapshot() -> dict[str, object]:
    return {
        "inducer": asdict(INDUCER),
        "judge": asdict(JUDGE),
        "sim_user": asdict(SIM_USER),
        "target_baseline": TARGET_BASELINE_MODEL,
        "target_downgraded": TARGET_DOWNGRADED_MODEL,
    }


def pinned_model_ids() -> frozenset[str]:
    return frozenset(
        {INDUCER_MODEL, JUDGE_MODEL, SIM_USER_MODEL, TARGET_BASELINE_MODEL, TARGET_DOWNGRADED_MODEL}
    )
