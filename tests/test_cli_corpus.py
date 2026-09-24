from typer.testing import CliRunner

from agentproof import cli
from agentproof.store import Store
from tests.factories import scenario, trace
from tests.fakes import EchoSession

runner = CliRunner()
AGENT = ["--adapter", "tests.fake_adapter", "--agent", "tests.fakes:echo_agent"]


def record(tmp_path, typed):
    return runner.invoke(cli.app, ["record", *AGENT, "--data", str(tmp_path)], input=typed)


def test_record_saves_the_conversation_as_a_seed(tmp_path):
    result = record(tmp_path, "\nhola\ngracias\n\n")
    assert result.exit_code == 0, result.output
    assert "agente> eco: hola" in result.output
    (seed,) = Store(tmp_path).seeds()
    assert [e.text for e in seed.events if e.kind == "user_message"] == ["hola", "gracias"]
    assert (seed.kind, seed.adapter, seed.variant) == ("seed", "tests.fake_adapter", "baseline")
    assert seed.termination == "user_ended"


def test_record_ends_on_end_of_input(tmp_path):
    result = record(tmp_path, "hola\n")
    assert result.exit_code == 0, result.output
    assert Store(tmp_path).seeds()[0].termination == "user_ended"


def test_record_saves_nothing_without_messages(tmp_path):
    result = record(tmp_path, "")
    assert result.exit_code == 1
    assert Store(tmp_path).seeds() == []


def test_record_rejects_an_agent_path_without_attribute(tmp_path):
    result = runner.invoke(
        cli.app, ["record", "--adapter", "tests.fake_adapter", "--agent", "tests.fakes"]
    )
    assert result.exit_code != 0


def test_induce_reports_created_and_failed_seeds(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.save_seed(trace(trace_id="tr-a"))
    store.save_seed(trace(trace_id="tr-b"))

    def fake_induce(seed):
        if seed.trace_id == "tr-b":
            raise RuntimeError("sin respuesta")
        return scenario(scenario_id="sc-tr-a", seed_trace_id="tr-a")

    monkeypatch.setattr(cli, "_induce", fake_induce)
    result = runner.invoke(cli.app, ["induce", "--data", str(tmp_path)])
    assert result.exit_code == 1
    assert "creado: sc-tr-a" in result.output and "falló: sc-tr-b" in result.output


def test_record_stores_the_card_of_the_session(tmp_path):
    result = runner.invoke(
        cli.app, ["record", *AGENT, "--card", "tc-03", "--data", str(tmp_path)], input="hola\n\n"
    )
    assert result.exit_code == 0, result.output
    assert Store(tmp_path).seeds()[0].card_id == "tc-03"


def test_record_without_a_card_leaves_it_empty(tmp_path):
    record(tmp_path, "hola\n\n")
    assert Store(tmp_path).seeds()[0].card_id is None


SEEN: list[EchoSession] = []


def spy_agent(variant: str) -> EchoSession:
    """Agent builder that keeps every session, to inspect what the agent received."""
    SEEN.append(EchoSession())
    return SEEN[-1]


def test_the_card_never_reaches_the_agent(tmp_path):
    SEEN.clear()
    args = [
        "record",
        "--adapter",
        "tests.fake_adapter",
        "--agent",
        "tests.test_cli_corpus:spy_agent",
    ]
    result = runner.invoke(
        cli.app, [*args, "--card", "tc-03", "--data", str(tmp_path)], input="hola\nadiós\n\n"
    )
    assert result.exit_code == 0, result.output
    (session,) = SEEN
    assert session.sent == ["hola", "adiós"]
    assert Store(tmp_path).seeds()[0].card_id == "tc-03"
