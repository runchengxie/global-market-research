"""One-attempt Paper orchestration: intents, limit commands, facts, projection."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Protocol

from apps.execution_runner.paper_state import AllocationState
from apps.execution_runner.safety import KillSwitch
from packages.contracts.orders import OrderIntent
from packages.execution_policies.paper_allocation import (
    AllocationError,
    Snapshot,
    aware,
    compute_allocation,
    number,
)


@dataclass(frozen=True)
class AccountSnapshot:
    account: str
    values: Snapshot
    positions: dict[str, Decimal]
    open_orders: tuple[str, ...]
    at: datetime


@dataclass(frozen=True)
class LimitCommand:
    intent: OrderIntent
    stage: str
    account: str
    con_id: int
    currency: str
    limit_price: Decimal
    tick: Decimal
    tif: str = "IOC"

    def to_dict(self):
        return {
            "order_id": self.intent.order_id,
            "symbol": self.intent.symbol,
            "side": self.intent.side,
            "quantity": str(self.intent.quantity),
            "stage": self.stage,
            "account": self.account,
            "con_id": self.con_id,
            "currency": self.currency,
            "limit_price": str(self.limit_price),
            "tick": str(self.tick),
            "tif": self.tif,
        }

    @classmethod
    def from_dict(cls, value):
        v = dict(value)
        intent = OrderIntent(
            v.pop("order_id"),
            v.pop("symbol"),
            v.pop("side"),
            Decimal(v.pop("quantity")),
        )
        return cls(
            intent=intent,
            **{
                k: Decimal(x) if k in ("limit_price", "tick") else x
                for k, x in v.items()
            },
        )


@dataclass(frozen=True)
class Outcome:
    status: str
    filled: Decimal
    remaining: Decimal
    average_price: Decimal
    broker_order_id: str
    executions: tuple[tuple[str, Decimal, Decimal], ...] = ()


class PaperBroker(Protocol):
    def prepare(self, spec) -> None: ...
    def snapshot(self) -> AccountSnapshot: ...
    def what_if(self, command: LimitCommand) -> None: ...
    def execute(
        self, command: LimitCommand, record: Callable[[Outcome], None]
    ) -> Outcome: ...
    def reconcile(self, commands, initial_positions) -> dict[str, Outcome]: ...


class PaperAllocationRunner:
    def __init__(
        self,
        spec,
        root,
        broker: PaperBroker | None,
        *,
        clock=None,
        kill_switch: KillSwitch | None = None,
    ):
        self.spec, self.broker = spec, broker
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        spec.validate(self.clock(), check_window=False)
        self.state = AllocationState(root, spec)
        self.kill_switch = kill_switch

    def plan(self, snapshot):
        self.spec.validate(self.clock(), check_window=False)
        return compute_allocation(self.spec.policy, snapshot, self.clock())

    def _check_submission_controls(self):
        self.spec.validate(self.clock())
        if (self.state.root / "STOP").exists():
            raise AllocationError("stopped")
        if self.kill_switch is not None:
            self.kill_switch.assert_clear()

    def _snapshot(self, initial=None):
        self._check_submission_controls()
        snap = self.broker.snapshot()
        self._check_submission_controls()
        if snap.account != self.spec.account or snap.open_orders:
            raise AllocationError("account_mismatch_or_open_orders")
        if not -1 <= (aware(self.clock()) - aware(snap.at)).total_seconds() <= 15:
            raise AllocationError("stale_account_snapshot")
        positions = {s: number(q) for s, q in snap.positions.items() if q != 0}
        if set(positions) - set(self.spec.allowed_positions):
            raise AllocationError("unexpected_positions")
        if initial is not None and positions != {
            s: q for s, q in initial.items() if q != 0
        }:
            raise AllocationError("positions_changed")
        # Validate all amounts, currencies and both live quotes on every recheck.
        compute_allocation(self.spec.policy, snap.values, self.clock())
        return snap

    def _command(self, stage, qty, price):
        stock = stage == "stock"
        return LimitCommand(
            OrderIntent(
                f"{self.spec.run_id}:{stage}",
                self.spec.symbol if stock else "USD/SGD",
                "BUY",
                Decimal(qty),
            ),
            stage,
            self.spec.account,
            self.spec.con_id if stock else 0,
            "USD" if stock else "SGD",
            price,
            self.spec.policy.stock_tick if stock else self.spec.policy.fx_tick,
        )

    def _record_outcome(self, command, out):
        number(out.filled)
        number(out.remaining)
        number(out.average_price)
        if (
            out.status
            not in {
                "pending",
                "submitted",
                "filled",
                "partial",
                "cancelled",
                "rejected",
                "unknown",
            }
            or out.filled + out.remaining > command.intent.quantity
            or out.filled > command.intent.quantity
        ):
            raise AllocationError("invalid_broker_outcome")
        if out.status == "filled" and (
            out.filled != command.intent.quantity or out.remaining != 0
        ):
            raise AllocationError("inconsistent_full_fill")
        seen = set()
        total = Decimal(0)
        for execution_id, quantity, price in out.executions:
            if not execution_id or execution_id in seen:
                raise AllocationError("invalid_execution_identity")
            seen.add(execution_id)
            total += number(quantity, positive=True)
            if number(price, positive=True) > command.limit_price:
                raise AllocationError("fill_outside_limit")
            self.state.record(
                f"fill:{execution_id}",
                "fill",
                order_id=command.intent.order_id,
                execution_id=execution_id,
                quantity=str(quantity),
                price=str(price),
            )
        if total != out.filled:
            raise AllocationError("execution_quantity_unconfirmed")
        self.state.record(
            f"{command.intent.order_id}:status:{out.status}:{out.filled}:{out.remaining}",
            "order_event",
            order_id=command.intent.order_id,
            status=out.status,
            filled=str(out.filled),
            remaining=str(out.remaining),
            average_price=str(out.average_price),
            broker_order_id=out.broker_order_id,
        )

    def _submit(self, command):
        self._check_submission_controls()
        self.state.mark_unresolved()
        self.state.record(
            command.intent.order_id + ":intent",
            "order_intent",
            order_id=command.intent.order_id,
            command=command.to_dict(),
        )
        self.state.record(
            command.intent.order_id + ":attempt",
            "submission_requested",
            order_id=command.intent.order_id,
            status="unknown",
        )
        self._check_submission_controls()
        out = self.broker.execute(
            command, lambda event: self._record_outcome(command, event)
        )
        self._record_outcome(command, out)
        return out

    def run(self):
        if self.broker is None:
            raise AllocationError("broker_required_for_submit")
        self.spec.validate(self.clock())
        with self.state.account_lock():
            self.state.claim()
            try:
                self.broker.prepare(self.spec)
                first = self._snapshot()
                initial = first.positions
                self.state.record(
                    "initial",
                    "initial_positions",
                    positions={s: str(q) for s, q in initial.items()},
                )
                plan = compute_allocation(self.spec.policy, first.values, self.clock())
                stock = self._command("stock", plan.shares, plan.stock_limit)
                self.broker.what_if(stock)
                if plan.usd_to_buy:
                    fx = self._command("fx", plan.usd_to_buy, plan.fx_limit)
                    self.broker.what_if(fx)
                    check = self._snapshot(initial)
                    replan = compute_allocation(
                        self.spec.policy, check.values, self.clock()
                    )
                    if replan != plan:
                        raise AllocationError("allocation_changed_before_fx")
                    out = self._submit(fx)
                    if out.status != "filled":
                        return (
                            "partial"
                            if out.filled
                            else "unknown"
                            if out.status == "unknown"
                            else "blocked"
                        )
                fresh = self._snapshot(initial)
                latest = compute_allocation(
                    self.spec.policy, fresh.values, self.clock()
                )
                qty = min(plan.shares, latest.shares)
                stock = self._command("stock", qty, plan.stock_limit)
                self.broker.what_if(stock)
                final = self._snapshot(initial)
                final_plan = compute_allocation(
                    self.spec.policy, final.values, self.clock()
                )
                needed = qty * plan.stock_limit * (1 + self.spec.policy.cash_buffer)
                if (
                    final_plan.stock_limit > plan.stock_limit
                    or final_plan.shares < qty
                    or min(final.values.usd_cash, final.values.usd_settled) < needed
                ):
                    raise AllocationError("stock_budget_or_quote_changed")
                out = self._submit(stock)
                if out.status != "filled":
                    return (
                        "partial"
                        if out.filled
                        else "unknown"
                        if out.status == "unknown"
                        else "blocked"
                    )
                expected = dict(initial)
                expected[self.spec.symbol] = (
                    expected.get(self.spec.symbol, Decimal(0)) + out.filled
                )
                self._verify_positions(expected)
                self.state.record("reconciled", "run_reconciled", status="reconciled")
                self.state.clear_unresolved()
                return "reconciled"
            except Exception as exc:
                status = "unknown" if self.state.unresolved() else "blocked"
                self.state.record(
                    "failure",
                    "run_error",
                    status=status,
                    reason=str(exc)
                    if isinstance(exc, AllocationError)
                    else "broker_or_io_error",
                )
                return status

    def _verify_positions(self, expected):
        snap = self.broker.snapshot()
        if (
            snap.account != self.spec.account
            or snap.open_orders
            or not -1 <= (aware(self.clock()) - aware(snap.at)).total_seconds() <= 15
            or {s: q for s, q in snap.positions.items() if q != 0}
            != {s: q for s, q in expected.items() if q != 0}
        ):
            raise AllocationError("reconciliation_unconfirmed")

    def reconcile(self):
        if self.broker is None:
            raise AllocationError("broker_required_for_reconciliation")
        with self.state.account_lock():
            self.state.assert_claim()
            events = self.state.journal.read()
            if any(e["kind"] == "run_reconciled" for e in events):
                self.state.clear_unresolved()
                return "reconciled"
            commands = [
                LimitCommand.from_dict(e["command"])
                for e in events
                if e["kind"] == "order_intent"
            ]
            initial = next(
                (e["positions"] for e in events if e["kind"] == "initial_positions"),
                None,
            )
            if not commands or initial is None:
                return "unknown"
            positions = {s: Decimal(q) for s, q in initial.items()}
            # Reconciliation must not require the historical submission window.
            getattr(self.broker, "prepare_reconciliation", self.broker.prepare)(
                self.spec
            )
            observations = self.broker.reconcile(commands, positions)
            if set(observations) != {c.intent.order_id for c in commands}:
                return "unknown"
            for command in commands:
                out = observations[command.intent.order_id]
                self._record_outcome(command, out)
                if out.status not in {"filled", "cancelled", "rejected"}:
                    return "partial" if out.filled else "unknown"
                if command.stage == "stock":
                    positions[self.spec.symbol] = (
                        positions.get(self.spec.symbol, Decimal(0)) + out.filled
                    )
            self._verify_positions(positions)
            self.state.record("reconciled", "run_reconciled", status="reconciled")
            self.state.clear_unresolved()
            return "reconciled"
