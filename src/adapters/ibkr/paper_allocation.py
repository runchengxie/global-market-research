"""Explicit optional IBKR port for cash-backed Paper IOC allocations."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import time
from zoneinfo import ZoneInfo

from apps.execution_runner.paper_allocation import AccountSnapshot, Outcome
from packages.execution_policies.paper_allocation import (
    AllocationError,
    Quote,
    Snapshot,
    aware,
    number,
)


class IBKRPaperAllocationBroker:
    def __init__(
        self, ib=None, *, clock=None, observation_seconds=45, cancellation_seconds=10
    ):
        if ib is None:
            from ib_insync import IB

            ib = IB()
        self.ib = ib
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if not 0 < observation_seconds <= 60 or not 0 < cancellation_seconds <= 15:
            raise AllocationError("invalid_observation_timeout")
        self.observation_seconds, self.cancellation_seconds = (
            observation_seconds,
            cancellation_seconds,
        )
        self.ib.RequestTimeout = 8
        self.errors = []
        if hasattr(self.ib, "errorEvent"):
            self.ib.errorEvent += self._error

    def _error(self, request_id, code, message, contract):
        self.errors.append(int(code))

    def _identity(self):
        if not self.ib.isConnected() or self.ib.managedAccounts() != [
            self.spec.account
        ]:
            raise AllocationError("paper_account_unverified")

    def prepare(self, spec):
        self._prepare(spec, reconciliation=False)

    def prepare_reconciliation(self, spec):
        self._prepare(spec, reconciliation=True)

    def _prepare(self, spec, *, reconciliation):
        from ib_insync import Forex, Stock

        spec.validate(self.clock(), check_window=not reconciliation)
        self.spec = spec
        if not self.ib.isConnected():
            self.ib.connect(
                spec.settings.gateway_host,
                spec.settings.gateway_port,
                clientId=spec.settings.client_id,
                readonly=reconciliation,
                timeout=8,
            )
        self._identity()
        contracts = self.ib.qualifyContracts(
            Stock(
                spec.symbol.removesuffix(".US"),
                "SMART",
                "USD",
                conId=spec.con_id,
                primaryExchange=spec.primary_exchange,
            ),
            Forex("USDSGD"),
        )
        if len(contracts) != 2:
            raise AllocationError("contract_qualification_failed")
        self.stock, self.fx = contracts
        if (
            self.stock.conId,
            self.stock.symbol,
            self.stock.secType,
            self.stock.currency,
            self.stock.exchange,
            self.stock.primaryExchange,
        ) != (
            spec.con_id,
            spec.symbol.removesuffix(".US"),
            "STK",
            "USD",
            "SMART",
            spec.primary_exchange,
        ):
            raise AllocationError("stock_contract_mismatch")
        if (self.fx.symbol, self.fx.secType, self.fx.currency, self.fx.exchange) != (
            "USD",
            "CASH",
            "SGD",
            "IDEALPRO",
        ) or self.fx.conId <= 0:
            raise AllocationError("fx_contract_mismatch")
        if reconciliation:
            return
        details = [self.ib.reqContractDetails(c) for c in (self.stock, self.fx)]
        if any(len(d) != 1 for d in details):
            raise AllocationError("contract_details_unverified")
        if (
            Decimal(str(details[0][0].minTick)),
            Decimal(str(details[1][0].minTick)),
        ) != (spec.policy.stock_tick, spec.policy.fx_tick):
            raise AllocationError("tick_mismatch")
        if not self._session_contains(
            details[0][0], spec.window_start, spec.window_end
        ):
            raise AllocationError("liquid_session_unverified")
        bars = self.ib.reqHistoricalData(
            self.stock,
            endDateTime="",
            durationStr="10 D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            timeout=8,
        )
        previous = [
            b for b in bars if str(b.date) == spec.policy.reference_date.isoformat()
        ]
        if (
            len(previous) != 1
            or abs(Decimal(str(previous[0].close)) - spec.policy.reference_close)
            > spec.policy.stock_tick
        ):
            raise AllocationError("reference_close_unverified")

    @staticmethod
    def _session_contains(details, start, end):
        try:
            tz = ZoneInfo(details.timeZoneId)
            for interval in details.liquidHours.split(";"):
                if "CLOSED" in interval:
                    continue
                for window in interval.split(","):
                    left, right = window.split("-")
                    a = datetime.strptime(left, "%Y%m%d:%H%M").replace(tzinfo=tz)
                    b = datetime.strptime(right, "%Y%m%d:%H%M").replace(tzinfo=tz)
                    if aware(a) <= aware(start) <= aware(end) <= aware(b):
                        return True
        except (ValueError, AttributeError, KeyError):
            pass
        return False

    def snapshot(self):
        self._identity()
        account = self.spec.account
        rows, observed_at = self._download_account_values()
        if any(v.account != account for v in rows):
            raise AllocationError("account_value_identity_mismatch")

        def value(tag, currency):
            matches = [v.value for v in rows if v.tag == tag and v.currency == currency]
            if len(matches) != 1:
                raise AllocationError("account_value_unavailable")
            return number(Decimal(matches[0]))

        def settled(currency):
            matches = [
                v.value
                for v in rows
                if v.tag == "SettledCashByDate" and v.currency == currency
            ]
            if len(matches) != 1:
                raise AllocationError("settled_cash_unverified")
            try:
                dated = {}
                for item in matches[0].split(";"):
                    day, amount = item.split(":")
                    if (
                        day in dated
                        or datetime.strptime(day, "%Y%m%d").strftime("%Y%m%d") != day
                    ):
                        raise ValueError()
                    dated[day] = number(Decimal(amount))
                today = (
                    self.clock()
                    .astimezone(ZoneInfo("Asia/Singapore"))
                    .strftime("%Y%m%d")
                )
                return dated[today]
            except (ValueError, KeyError, InvalidOperation) as exc:
                raise AllocationError("settled_cash_unverified") from exc

        positions = {}
        for pos in self.ib.reqPositions():
            if pos.account != account or not pos.position:
                continue
            c = pos.contract
            if c.secType != "STK":
                raise AllocationError("unexpected_position_type")
            suffix = {"USD": ".US", "JPY": ".T", "HKD": ".HK"}.get(c.currency)
            if suffix is None:
                raise AllocationError("unexpected_position_currency")
            symbol = c.symbol + suffix
            positions[symbol] = positions.get(symbol, Decimal(0)) + Decimal(
                str(pos.position)
            )
            if symbol == self.spec.symbol and c.conId != self.spec.con_id:
                raise AllocationError("position_contract_mismatch")
        open_orders = tuple(
            str(t.order.orderId)
            for t in self.ib.reqAllOpenOrders()
            if t.order.account == account
        )
        stock, fx = self._quotes()
        values = Snapshot(
            value("NetLiquidation", "SGD"),
            value("GrossPositionValue", "SGD"),
            value("$LEDGER-CashBalance", "SGD"),
            value("$LEDGER-CashBalance", "USD"),
            settled("SGD"),
            settled("USD"),
            stock,
            fx,
        )
        return AccountSnapshot(account, values, positions, open_orders, observed_at)

    def _download_account_values(self):
        account = self.spec.account
        rows = {}
        observed = []

        def capture(value):
            if value.account == account:
                rows[(value.tag, value.currency, value.modelCode)] = value
                observed.append(self.clock())

        # A dedicated client owns this subscription. reqAccountUpdates waits for
        # accountDownloadEnd; capture only rows received during this download.
        self.ib.client.reqAccountUpdates(False, account)
        self.ib.accountValueEvent += capture
        try:
            self.ib.reqAccountUpdates(account)
        finally:
            self.ib.accountValueEvent -= capture
            self.ib.client.reqAccountUpdates(False, account)
        if not observed:
            raise AllocationError("fresh_account_download_required")
        return list(rows.values()), min(observed)

    def _quotes(self):
        self.ib.reqMarketDataType(1)
        tickers = []
        try:
            for contract in (self.stock, self.fx):
                tickers.append(
                    (contract, self.ib.reqMktData(contract, "", False, False))
                )
            end = time.monotonic() + 8
            while time.monotonic() < end:
                if all(t.time is not None for _, t in tickers):
                    break
                self.ib.sleep(0.1)
            return tuple(
                Quote(
                    Decimal(str(t.bid)),
                    Decimal(str(t.ask)),
                    t.time,
                    t.marketDataType == 1,
                )
                for _, t in tickers
            )
        finally:
            for contract, _ in tickers:
                self.ib.cancelMktData(contract)

    def _translate(self, command):
        from ib_insync import LimitOrder

        self._identity()
        stock = command.stage == "stock"
        contract = self.stock if stock else self.fx
        if (
            command.stage not in {"stock", "fx"}
            or command.account != self.spec.account
            or command.intent.order_id != f"{self.spec.run_id}:{command.stage}"
            or command.intent.symbol != (self.spec.symbol if stock else "USD/SGD")
            or command.currency != ("USD" if stock else "SGD")
            or command.con_id != (self.spec.con_id if stock else 0)
            or command.intent.side != "BUY"
            or command.tif != "IOC"
            or command.tick
            != (self.spec.policy.stock_tick if stock else self.spec.policy.fx_tick)
            or number(command.limit_price, positive=True) % command.tick != 0
            or number(command.intent.quantity, positive=True) % 1 != 0
        ):
            raise AllocationError("invalid_limit_command")
        order = LimitOrder(
            "BUY",
            float(command.intent.quantity),
            float(command.limit_price),
            tif="IOC",
            account=command.account,
            orderRef=command.intent.order_id,
        )
        return contract, order

    def what_if(self, command):
        contract, order = self._translate(command)
        self.errors.clear()
        state = self.ib.run(
            asyncio.wait_for(self.ib.whatIfOrderAsync(contract, order), 8)
        )
        if (
            state is None
            or state.status not in {"PreSubmitted", "Submitted"}
            or state.warningText
        ):
            raise AllocationError("what_if_rejected")
        if any(c in {201, 321, 354} for c in self.errors):
            raise AllocationError("what_if_error")
        values = [
            Decimal(str(getattr(state, key)))
            for key in (
                "initMarginChange",
                "maintMarginChange",
                "equityWithLoanChange",
                "commission",
            )
        ]
        if (
            any(not v.is_finite() or abs(v) >= Decimal("1e100") for v in values)
            or values[-1] < 0
        ):
            raise AllocationError("what_if_unavailable")

    def execute(self, command, record):
        contract, order = self._translate(command)
        self.spec.validate(self.clock())
        trade = self.ib.placeOrder(contract, order)
        end = time.monotonic() + self.observation_seconds
        while not trade.isDone() and self.ib.isConnected() and time.monotonic() < end:
            self.ib.sleep(0.1)
        if not trade.isDone() and self.ib.isConnected():
            self.ib.cancelOrder(trade.order)
            end = time.monotonic() + self.cancellation_seconds
            while (
                not trade.isDone() and self.ib.isConnected() and time.monotonic() < end
            ):
                self.ib.sleep(0.1)
        outcome = self._outcome(command, trade)
        record(outcome)
        return outcome

    def _outcome(self, command, trade):
        status = trade.orderStatus
        executions = []
        for fill in trade.fills:
            e = fill.execution
            expected_con_id = (
                self.stock.conId if command.stage == "stock" else self.fx.conId
            )
            if (
                e.acctNumber != self.spec.account
                or fill.contract.conId != expected_con_id
                or e.side != "BOT"
                or e.orderId != trade.order.orderId
                or e.orderRef != command.intent.order_id
            ):
                raise AllocationError("fill_identity_mismatch")
            row = (e.execId, Decimal(str(e.shares)), Decimal(str(e.price)))
            if row not in executions:
                executions.append(row)
        filled = Decimal(str(status.filled))
        remaining = Decimal(str(status.remaining))
        result = {
            "Filled": "filled",
            "Cancelled": "cancelled",
            "ApiCancelled": "cancelled",
            "Inactive": "rejected",
        }.get(status.status, "unknown")
        if filled > 0 and result != "filled":
            result = "partial"
        return Outcome(
            result,
            filled,
            remaining,
            Decimal(str(status.avgFillPrice)),
            str(trade.order.orderId),
            tuple(executions),
        )

    def reconcile(self, commands, initial_positions):
        self._identity()
        completed = self.ib.reqCompletedOrders(apiOnly=False)
        fills = self.ib.reqExecutions()
        result = {}
        for command in commands:
            matches = [
                t
                for t in completed
                if t.order.account == self.spec.account
                and t.order.orderRef == command.intent.order_id
            ]
            if len(matches) != 1:
                continue
            trade = matches[0]
            expected = self.stock.conId if command.stage == "stock" else self.fx.conId
            if (
                trade.contract.conId != expected
                or trade.order.action != "BUY"
                or Decimal(str(trade.order.totalQuantity)) != command.intent.quantity
                or Decimal(str(trade.order.lmtPrice)) != command.limit_price
                or trade.order.tif != "IOC"
            ):
                raise AllocationError("completed_order_identity_mismatch")
            trade.fills = [
                f
                for f in fills
                if f.execution.acctNumber == self.spec.account
                and f.execution.orderRef == command.intent.order_id
            ]
            result[command.intent.order_id] = self._outcome(command, trade)
        return result

    def close(self):
        if self.ib.isConnected():
            self.ib.disconnect()
