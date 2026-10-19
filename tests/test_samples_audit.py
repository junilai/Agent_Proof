from collections import Counter

from agentproof.store import Store
from experiments.samples import AUDIT_PER_CONDITION, audit_sample, has_ticket, ticket_share
from tests.factories import event, manifest, trace

TICKET = [event(1, "user_message", text="hola"), event(2, "tool_call", tool="create_ticket")]
PLAIN = [event(1, "user_message", text="hola"), event(2, "agent_message", text="listo")]


def run_with(store, condition, tickets, plain, invalid=0):
    """A run of ``condition`` with that many traces with a ticket, without one and invalid."""
    run_id = f"{condition}-20261018-000000"
    variant = "baseline" if condition.startswith("baseline") else condition
    store.create_run(manifest(run_id=run_id, condition=condition, variant=variant))
    kinds = [TICKET] * tickets + [PLAIN] * plain + [PLAIN] * invalid
    for n, events in enumerate(kinds, start=1):
        store.save_run_trace(
            trace(
                "run",
                events=events,
                trace_id=f"tr-{condition[:2]}{condition[-1]}{n:09d}",
                run_id=run_id,
                condition=condition,
                variant=variant,
                repetition=n,
                termination="simulator_error" if n > tickets + plain else "user_ended",
            )
        )
    return run_id


def test_a_ticket_is_a_create_ticket_call():
    assert has_ticket(trace("run", events=TICKET))
    assert not has_ticket(trace("run", events=PLAIN))


def test_three_with_ticket_and_two_without_per_condition(tmp_path):
    store = Store(tmp_path)
    runs = [run_with(store, c, tickets=6, plain=6) for c in ("baseline-a", "d1")]
    drawn = audit_sample(store, runs)
    assert Counter((d.condition, d.stratum) for d in drawn) == {
        ("baseline-a", "con ticket"): 3,
        ("baseline-a", "sin ticket"): 2,
        ("d1", "con ticket"): 3,
        ("d1", "sin ticket"): 2,
    }
    assert len({d.trace_id for d in drawn}) == 2 * AUDIT_PER_CONDITION


def test_a_condition_short_of_tickets_is_completed_without_them(tmp_path):
    store = Store(tmp_path)
    drawn = audit_sample(store, [run_with(store, "d6", tickets=1, plain=8)])
    assert Counter(d.stratum for d in drawn) == {"con ticket": 1, "sin ticket": 4}


def test_invalid_repetitions_are_never_drawn(tmp_path):
    store = Store(tmp_path)
    run = run_with(store, "d2", tickets=3, plain=2, invalid=5)
    drawn = {d.trace_id for d in audit_sample(store, [run])}
    valid = {t.trace_id for t in store.run_traces(run) if t.termination != "simulator_error"}
    assert drawn == valid


def test_the_draw_is_reproducible(tmp_path):
    store = Store(tmp_path)
    runs = [run_with(store, c, tickets=10, plain=10) for c in ("baseline-a", "d4")]
    assert audit_sample(store, runs) == audit_sample(store, list(reversed(runs)))


def test_ticket_share_counts_valid_traces_per_condition(tmp_path):
    """The real share of each stratum, to weight the audit's error rate."""
    store = Store(tmp_path)
    runs = [run_with(store, "d5", tickets=2, plain=6, invalid=3)]
    assert ticket_share(store, runs) == {"d5": (2, 8)}
