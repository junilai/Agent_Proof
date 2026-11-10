import pytest

from agentproof.adapters.crewai import (
    TELEMETRY_VARS,
    TelemetryEnabledError,
    ensure_no_telemetry,
)
from tests.fakes_crewai import TELEMETRY_OFF, offline


@pytest.fixture(autouse=True)
def network(monkeypatch):
    return offline(monkeypatch)


@pytest.mark.parametrize("var", TELEMETRY_VARS)
@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "True"])
def test_any_crewai_switch_turns_telemetry_off(var, value):
    ensure_no_telemetry({var: value, "CREWAI_TRACING_ENABLED": "false"})


def test_refuses_with_telemetry_on():
    with pytest.raises(TelemetryEnabledError, match="CREWAI_DISABLE_TELEMETRY=true"):
        ensure_no_telemetry({"CREWAI_TRACING_ENABLED": "false"})
    with pytest.raises(TelemetryEnabledError, match="CREWAI_DISABLE_TELEMETRY"):
        ensure_no_telemetry({"CREWAI_DISABLE_TELEMETRY": "false"})


@pytest.mark.parametrize("value", ["true", "1"])
def test_refuses_with_tracing_on(value):
    env = {**TELEMETRY_OFF, "CREWAI_TRACING_ENABLED": value}
    with pytest.raises(TelemetryEnabledError, match="CREWAI_TRACING_ENABLED=false"):
        ensure_no_telemetry(env)


def test_refuses_when_crewai_itself_would_send_traces(monkeypatch):
    """A consent stored by ``crewai traces enable`` turns tracing on without any variable."""
    monkeypatch.setattr("agentproof.adapters.crewai.should_enable_tracing", lambda *a, **k: True)
    with pytest.raises(TelemetryEnabledError, match="CREWAI_TRACING_ENABLED=false"):
        ensure_no_telemetry(TELEMETRY_OFF)


def test_refuses_when_crewai_itself_reads_telemetry_on(monkeypatch):
    monkeypatch.delenv("CREWAI_DISABLE_TELEMETRY")
    monkeypatch.delenv("CREWAI_DISABLE_TRACKING")
    monkeypatch.delenv("OTEL_SDK_DISABLED")
    with pytest.raises(TelemetryEnabledError, match="CREWAI_DISABLE_TELEMETRY"):
        ensure_no_telemetry(TELEMETRY_OFF)


def test_telemetry_and_tracing_off_is_fine():
    ensure_no_telemetry(TELEMETRY_OFF)
