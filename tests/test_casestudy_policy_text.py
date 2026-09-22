from casestudy.domain.policy import RefundPolicy
from casestudy.domain.policy_text import policy_text


def test_text_states_every_parameter_of_the_true_policy():
    text = policy_text()
    for fragment in ("30 días", "$500", "365 días", "tarjetas de regalo", "software descargable"):
        assert fragment in text


def test_text_follows_the_parameters():
    corrupted = RefundPolicy(window_days=90, supervisor_threshold_usd=1000.0, warranty_days=540)
    text = policy_text(corrupted)
    assert "90 días" in text and "$1000" in text and "540 días" in text
    assert "30 días" not in text and "$500" not in text


def test_text_names_the_three_outcomes_and_forbids_other_remedies():
    text = policy_text()
    assert "procede" in text and "no procede" in text and "se escala" in text
    assert "No se ofrecen reembolsos parciales ni crédito en tienda." in text
