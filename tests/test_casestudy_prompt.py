from datetime import date

from casestudy.domain.prompt import SYSTEM_PROMPT, spanish_date


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
