import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace as N

import pytest

from adapters.ibkr.paper_allocation import IBKRPaperAllocationBroker
from apps.execution_runner.paper_allocation import LimitCommand
from apps.execution_runner.paper_spec import AllocationSpec
from packages.contracts.orders import OrderIntent
from packages.execution_policies.paper_allocation import (
    AllocationError,
    AllocationPolicy,
)

NOW = datetime(2026, 11, 6, 15, tzinfo=timezone.utc)


def spec():
    return AllocationSpec.from_dict(
        {
            "schema": "paper-allocation.v1",
            "run_id": "demo",
            "account": "DU123456",
            "symbol": "TEST.US",
            "con_id": 123,
            "primary_exchange": "ARCA",
            "window_start": "2026-11-06T14:59:00+00:00",
            "window_end": "2026-11-06T15:10:00+00:00",
            "policy": {
                **{
                    k: str(v)
                    for k, v in vars(
                        AllocationPolicy(
                            D(".5"),
                            D("20000"),
                            500,
                            D("100"),
                            date(2026, 11, 5),
                            D(".01"),
                            D(".00005"),
                        )
                    ).items()
                },
                "max_shares": 500,
                "reference_date": "2026-11-05",
            },
            "allowed_positions": ["TEST.US"],
            "settings": {
                "environment": "paper",
                "gateway_host": "127.0.0.1",
                "gateway_port": 4002,
                "client_id": 123,
                "dry_run": False,
                "live_enabled": False,
            },
        }
    )


class IB:
    def __init__(self):
        self.connected = False
        self.account = "DU123456"
        self.placed = []
        self.cancelled = []
        self.status = "Filled"
        self.sleep_count = 0

    def connect(self, host, port, **kw):
        self.connected = True

    def isConnected(self):
        return self.connected

    def disconnect(self):
        self.connected = False

    def managedAccounts(self):
        return [self.account]

    def qualifyContracts(self, stock, fx):
        stock.conId, stock.primaryExchange = 123, "ARCA"
        fx.conId = 456
        return [stock, fx]

    def reqContractDetails(self, contract):
        return [
            N(
                minTick=0.01 if contract.secType == "STK" else 0.00005,
                timeZoneId="America/New_York",
                liquidHours="20261106:0930-20261106:1600",
            )
        ]

    def reqHistoricalData(self, *a, **kw):
        return [N(date=date(2026, 11, 5), close=100)]

    def reqAllOpenOrders(self):
        return []

    def reqPositions(self):
        return []

    def accountValues(self, account):
        return [
            N(account=self.account, tag=t, currency=c, value=v)
            for t, c, v in [
                ("NetLiquidation", "SGD", "10000"),
                ("GrossPositionValue", "SGD", "0"),
                ("$LEDGER-CashBalance", "SGD", "10000"),
                ("$LEDGER-CashBalance", "USD", "0"),
                ("SettledCashByDate", "SGD", "20261106:10000"),
                ("SettledCashByDate", "USD", "20261106:0"),
            ]
        ]

    def reqMarketDataType(self, kind):
        assert kind == 1

    def reqMktData(self, contract, *args):
        return N(
            bid=99.99 if contract.secType == "STK" else 1.3,
            ask=100 if contract.secType == "STK" else 1.301,
            time=NOW,
            marketDataType=1,
        )

    def cancelMktData(self, contract):
        pass

    def sleep(self, seconds):
        self.sleep_count += 1

    def run(self, awaitable):
        return asyncio.run(awaitable)

    async def whatIfOrderAsync(self, *args):
        return N(
            status="PreSubmitted",
            initMarginChange="0",
            maintMarginChange="0",
            equityWithLoanChange="0",
            commission="1",
            warningText="",
        )

    def placeOrder(self, contract, order):
        self.placed.append((contract, order))
        order.orderId = 7
        filled = order.totalQuantity if self.status == "Filled" else 0
        self.trade = N(
            order=order,
            contract=contract,
            orderStatus=N(
                status=self.status,
                filled=filled,
                remaining=order.totalQuantity - filled,
                avgFillPrice=order.lmtPrice,
            ),
            fills=[
                N(
                    contract=contract,
                    execution=N(
                        execId="exec-7",
                        acctNumber=self.account,
                        orderId=7,
                        orderRef=order.orderRef,
                        shares=filled,
                        price=order.lmtPrice,
                        side="BOT",
                    ),
                )
            ]
            if filled
            else [],
            isDone=lambda: self.status in ("Filled", "Cancelled"),
        )
        return self.trade

    def cancelOrder(self, order):
        self.cancelled.append(order.orderId)
        self.status = "Cancelled"
        self.trade.orderStatus.status = "Cancelled"

    def reqCompletedOrders(self, apiOnly):
        return []

    def reqExecutions(self, *args):
        return []


def broker(ib):
    obj = IBKRPaperAllocationBroker(
        ib, clock=lambda: NOW, observation_seconds=0.01, cancellation_seconds=0.01
    )
    obj.prepare(spec())
    return obj


def command():
    return LimitCommand(
        OrderIntent("demo:stock", "TEST.US", "BUY", D("2")),
        "stock",
        "DU123456",
        123,
        "USD",
        D("100.20"),
        D(".01"),
    )


def test_qualified_ioc_limit_preserves_intent_account_and_exec_identity():
    ib = IB()
    port = broker(ib)
    port.what_if(command())
    events = []
    out = port.execute(command(), events.append)
    assert out.status == "filled" and out.filled == 2
    assert out.executions == (("exec-7", D("2"), D("100.2")),)
    contract, order = ib.placed[0]
    assert contract.conId == 123
    assert (order.orderType, order.tif, order.account, order.orderRef) == (
        "LMT",
        "IOC",
        "DU123456",
        "demo:stock",
    )
    assert events[-1] == out


def test_mismatched_paper_account_never_qualifies_or_submits():
    ib = IB()
    ib.account = "DU999999"
    with pytest.raises(AllocationError):
        broker(ib)
    assert ib.placed == []


def test_snapshot_checks_explicit_settled_cash_and_live_quotes():
    port = broker(IB())
    snap = port.snapshot()
    assert snap.values.sgd_settled == 10000
    assert snap.values.stock.live is True
    assert snap.account == "DU123456"


def test_bounded_timeout_requests_cancellation_without_retry():
    ib = IB()
    ib.status = "Submitted"
    port = broker(ib)
    out = port.execute(command(), lambda e: None)
    assert out.status == "cancelled"
    assert ib.cancelled == [7]
    assert len(ib.placed) == 1


def test_reconcile_missing_broker_evidence_is_unknown_and_read_only():
    ib = IB()
    port = broker(ib)
    assert port.reconcile([command()], {}) == {}
    assert ib.placed == [] and ib.cancelled == []
