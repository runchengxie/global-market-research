from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from apps.execution_runner.paper_spec import AllocationSpec
from apps.execution_runner.paper_allocation import (
    AccountSnapshot,
    Outcome,
    PaperAllocationRunner,
)
from packages.execution_policies.paper_allocation import AllocationError
from test_paper_allocation_policy import NOW, policy, snapshot


def spec(run_id="example-run"):
    return AllocationSpec(
        run_id=run_id,
        account="DU123456",
        symbol="TEST.US",
        con_id=123,
        primary_exchange="ARCA",
        window_start=NOW - timedelta(minutes=1),
        window_end=NOW + timedelta(minutes=10),
        policy=policy(),
        allowed_positions=("TEST.US",),
    )


class Broker:
    def __init__(self, fx="filled", stock="filled"):
        self.values = snapshot()
        self.positions = {"TEST.US": D("0")}
        self.fx, self.stock = fx, stock
        self.commands = []
        self.on_what_if = lambda cmd: None
        self.reconciled = False

    def prepare(self, config):
        self.config = config

    def snapshot(self):
        return AccountSnapshot("DU123456", self.values, dict(self.positions), (), NOW)

    def what_if(self, command):
        self.on_what_if(command)

    def execute(self, command, record):
        self.commands.append(command)
        status = self.fx if command.stage == "fx" else self.stock
        if status == "disconnect":
            raise OSError("lost response")
        qty = (
            command.intent.quantity
            if status == "filled"
            else D("1")
            if status == "partial"
            else D("0")
        )
        if command.stage == "fx" and status == "filled":
            self.values = replace(
                self.values,
                usd_cash=qty,
                usd_settled=qty,
                sgd_cash=D("5000"),
                sgd_settled=D("5000"),
            )
        if command.stage == "stock":
            self.positions["TEST.US"] += qty
        outcome = Outcome(
            status,
            qty,
            command.intent.quantity - qty,
            command.limit_price if qty else D(0),
            str(len(self.commands)),
            ((f"exec-{len(self.commands)}", qty, command.limit_price),) if qty else (),
        )
        record(outcome)
        return outcome

    def reconcile(self, commands, initial_positions):
        return (
            {
                c.intent.order_id: Outcome(
                    "filled",
                    c.intent.quantity,
                    D(0),
                    c.limit_price,
                    str(i),
                    ((f"exec-{i}", c.intent.quantity, c.limit_price),),
                )
                for i, c in enumerate(commands, 1)
            }
            if self.reconciled
            else {}
        )


def run(root, broker=None, config=None):
    return PaperAllocationRunner(config or spec(), root, broker, clock=lambda: NOW)


def test_default_plan_does_not_connect_claim_or_submit(tmp_path):
    report = run(tmp_path).plan(snapshot())
    assert report.shares == 38
    assert list(tmp_path.iterdir()) == []


def test_fx_must_fill_before_stock_and_journal_projection_is_replayable(tmp_path):
    broker = Broker()
    result = run(tmp_path, broker).run()
    assert result == "reconciled"
    assert [c.stage for c in broker.commands] == ["fx", "stock"]
    assert all(c.intent.side == "BUY" and c.tif == "IOC" for c in broker.commands)
    journal = run(tmp_path, broker).state.journal
    projection = journal.rebuild_projection()
    assert projection["example-run:stock"]["status"] == "filled"
    assert len([e for e in journal.read() if e["kind"] == "fill"]) == 2
    with pytest.raises((AllocationError, FileExistsError)):
        run(tmp_path, broker).run()
    assert len(broker.commands) == 2


@pytest.mark.parametrize("fx", ["partial", "cancelled", "unknown", "disconnect"])
def test_nonfilled_fx_blocks_stock_and_every_new_run_id(tmp_path, fx):
    broker = Broker(fx=fx)
    assert run(tmp_path, broker).run() in {"partial", "blocked", "unknown"}
    assert [c.stage for c in broker.commands] == ["fx"]
    with pytest.raises((AllocationError, FileExistsError)):
        run(tmp_path, Broker(), spec("different-run")).run()


def test_what_if_position_change_blocks_submission(tmp_path):
    broker = Broker()
    broker.on_what_if = lambda cmd: broker.positions.update({"TEST.US": D("1")})
    assert run(tmp_path, broker).run() == "blocked"
    assert broker.commands == []


def test_stop_written_during_what_if_blocks_submission(tmp_path):
    broker = Broker()
    broker.on_what_if = lambda cmd: (tmp_path / "STOP").touch()
    assert run(tmp_path, broker).run() == "blocked"
    assert broker.commands == []


def test_incomplete_reconciliation_never_clears_account_block(tmp_path):
    broker = Broker(fx="disconnect")
    assert run(tmp_path, broker).run() == "unknown"
    assert run(tmp_path, broker).reconcile() == "unknown"
    with pytest.raises((AllocationError, FileExistsError)):
        run(tmp_path, Broker(), spec("next-run")).run()


def test_reconciliation_is_read_only_deduplicates_and_can_clear_confirmed_attempt(
    tmp_path,
):
    broker = Broker(fx="disconnect")
    assert run(tmp_path, broker).run() == "unknown"
    broker.reconciled = True
    runner = run(tmp_path, broker)
    assert runner.reconcile() == "reconciled"
    before = runner.state.journal.read()
    assert runner.reconcile() == "reconciled"
    assert runner.state.journal.read() == before
    assert len(broker.commands) == 1


def test_strict_spec_rejects_live_unknown_fields_and_naive_window():
    with pytest.raises(AllocationError):
        replace(spec(), account="U123456").validate(NOW)
    with pytest.raises(AllocationError):
        replace(spec(), window_start=NOW.replace(tzinfo=None)).validate(NOW)
    with pytest.raises(AllocationError):
        AllocationSpec.from_dict({"schema": "paper-allocation.v1", "unexpected": True})


def test_storage_alias_prevents_duplicate_attempt(tmp_path):
    root = tmp_path / "global-market-research" / "paper-allocation"
    broker = Broker(fx="disconnect")
    assert run(root, broker).run() == "unknown"
    alias = tmp_path / "2026-quant-competition" / "paper-allocation"
    with pytest.raises((AllocationError, FileExistsError)):
        run(alias, Broker(), spec("another-run")).run()


def test_reconcile_clears_marker_after_crash_between_receipt_and_clear(tmp_path):
    broker = Broker()
    runner = run(tmp_path, broker)
    assert runner.run() == "reconciled"
    runner.state.mark_unresolved()  # receipt durable, marker removal was lost
    assert runner.reconcile() == "reconciled"
    assert runner.state.unresolved() == []


@pytest.mark.parametrize("snapshot_number", [2, 4])
def test_stop_created_during_final_snapshot_prevents_next_submission(
    tmp_path, snapshot_number
):
    class StoppingBroker(Broker):
        count = 0

        def snapshot(self):
            self.count += 1
            if self.count == snapshot_number:
                (tmp_path / "STOP").touch()
            return super().snapshot()

    broker = StoppingBroker()
    result = run(tmp_path, broker).run()
    assert result in {"blocked", "unknown"}
    assert [c.stage for c in broker.commands] == (
        [] if snapshot_number == 2 else ["fx"]
    )


def test_process_death_releases_account_lock_for_reconciliation(tmp_path):
    import subprocess
    import sys
    import os

    code = """
import json,os,sys
from apps.execution_runner.paper_spec import AllocationSpec
from apps.execution_runner.paper_state import AllocationState
state=AllocationState(sys.argv[1],AllocationSpec.from_dict(json.loads(sys.argv[2])))
with state.account_lock():
    os._exit(0)
"""
    import json

    env = {
        **os.environ,
        "PYTHONPATH": str(
            __import__("pathlib").Path(__file__).resolve().parents[2] / "src"
        ),
    }
    subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), json.dumps(spec().to_dict())],
        env=env,
        check=True,
    )
    with run(tmp_path).state.account_lock():
        pass
