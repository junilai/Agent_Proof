import hashlib
from datetime import date

from casestudy.domain.mutations import APPROVE_EVERYTHING, BASELINE, MUTATIONS
from casestudy.domain.prompt import SYSTEM_PROMPT, spanish_date, system_prompt


def test_spanish_date():
    assert spanish_date(date(2026, 10, 1)) == "1 de octubre de 2026"
    assert spanish_date(date(2025, 3, 15)) == "15 de marzo de 2025"


def test_prompt_states_the_domain_date_and_the_tools():
    assert "Hoy es 1 de octubre de 2026." in SYSTEM_PROMPT
    for tool in ("lookup_order", "get_refund_policy", "create_ticket"):
        assert tool in SYSTEM_PROMPT


def test_prompt_never_states_the_policy_itself():
    for leak in ("30 días", "$500", "365", "tarjetas de regalo", "software descargable"):
        assert leak not in SYSTEM_PROMPT


BASELINE_FINGERPRINT = "5e43bc0391977c1a1d938e4a7e83026031dbd4c91ca9bf95bf9b4b50ee644acd"


def test_the_baseline_prompt_is_the_one_the_corpus_was_recorded_with():
    assert hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest() == BASELINE_FINGERPRINT
    assert system_prompt(BASELINE) == SYSTEM_PROMPT


def test_d2_drops_only_the_policy_check():
    trimmed = system_prompt(MUTATIONS["d2"])
    assert "get_refund_policy" not in trimmed
    assert set(trimmed.split("\n")) < set(SYSTEM_PROMPT.split("\n"))
    assert len(SYSTEM_PROMPT.split("\n")) - len(trimmed.split("\n")) == 1


def test_d5_adds_the_instruction_as_one_more_rule():
    injected = system_prompt(MUTATIONS["d5"])
    assert injected.startswith(SYSTEM_PROMPT)
    assert injected.endswith(f"\n- {APPROVE_EVERYTHING}")


def test_the_other_mutations_keep_the_prompt():
    for name in ("d1", "d3", "d4", "d6"):
        assert system_prompt(MUTATIONS[name]) == SYSTEM_PROMPT
