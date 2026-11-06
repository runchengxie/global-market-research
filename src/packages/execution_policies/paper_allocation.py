"""Cash-backed USD equity allocation valued in SGD; no broker dependencies."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


class AllocationError(ValueError):
    """An allocation precondition is missing or unsafe."""


def number(value, *, positive=False):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise AllocationError("invalid_decimal")
    if value < 0 or (positive and value == 0):
        raise AllocationError("invalid_decimal")
    return value


def aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AllocationError("timezone_required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Quote:
    bid: Decimal
    ask: Decimal
    at: datetime
    live: bool

    def validate(self, now, max_spread):
        bid, ask = number(self.bid, positive=True), number(self.ask, positive=True)
        age = (aware(now) - aware(self.at)).total_seconds()
        if self.live is not True or not -1 <= age <= 15:
            raise AllocationError("fresh_live_quote_required")
        if bid > ask or (ask - bid) / ask > max_spread:
            raise AllocationError("crossed_or_wide_quote")


@dataclass(frozen=True)
class AllocationPolicy:
    target_weight: Decimal
    max_target_sgd: Decimal
    max_shares: int
    reference_close: Decimal
    reference_date: date
    stock_tick: Decimal
    fx_tick: Decimal
    stock_spread: Decimal = Decimal('.005')
    fx_spread: Decimal = Decimal('.003')
    stock_slippage: Decimal = Decimal('.002')
    fx_slippage: Decimal = Decimal('.0005')
    cash_buffer: Decimal = Decimal('.005')
    reference_band: Decimal = Decimal('.015')

    def validate(self, now):
        for value in (self.max_target_sgd, self.reference_close, self.stock_tick, self.fx_tick):
            number(value, positive=True)
        if not 0 < number(self.target_weight) <= 1:
            raise AllocationError("invalid_target_weight")
        if type(self.max_shares) is not int or self.max_shares < 1:
            raise AllocationError("invalid_share_cap")
        for value in (self.stock_spread, self.fx_spread, self.stock_slippage,
                      self.fx_slippage, self.cash_buffer, self.reference_band):
            if number(value) > Decimal('.05'):
                raise AllocationError("policy_tolerance_too_large")
        if type(self.reference_date) is not date or self.reference_date >= aware(now).date():
            raise AllocationError("invalid_reference_date")


@dataclass(frozen=True)
class Snapshot:
    nav_sgd: Decimal
    gross_sgd: Decimal
    sgd_cash: Decimal
    usd_cash: Decimal
    sgd_settled: Decimal
    usd_settled: Decimal
    stock: Quote
    fx: Quote
    account_currency: str = "SGD"
    stock_currency: str = "USD"
    fx_pair: str = "USD/SGD"


@dataclass(frozen=True)
class AllocationPlan:
    shares: int
    stock_limit: Decimal
    fx_limit: Decimal
    stock_notional_usd: Decimal
    usd_to_buy: Decimal
    sgd_required: Decimal
    target_sgd: Decimal


def round_up(value, tick):
    return (value / tick).to_integral_value(rounding=ROUND_CEILING) * tick


def compute_allocation(policy: AllocationPolicy, snapshot: Snapshot, now: datetime) -> AllocationPlan:
    policy.validate(now)
    if (snapshot.account_currency, snapshot.stock_currency, snapshot.fx_pair) != ('SGD', 'USD', 'USD/SGD'):
        raise AllocationError("unsupported_currency_contract")
    nav = number(snapshot.nav_sgd, positive=True)
    gross = number(snapshot.gross_sgd)
    sgd = min(number(snapshot.sgd_cash), number(snapshot.sgd_settled))
    usd = min(number(snapshot.usd_cash), number(snapshot.usd_settled))
    snapshot.stock.validate(now, policy.stock_spread)
    snapshot.fx.validate(now, policy.fx_spread)
    if abs(snapshot.stock.ask / policy.reference_close - 1) > policy.reference_band:
        raise AllocationError("outside_reference_band")
    target = nav * policy.target_weight
    if target > policy.max_target_sgd or gross >= target:
        raise AllocationError("target_out_of_bounds_or_reached")
    stock_limit = round_up(snapshot.stock.ask * (1 + policy.stock_slippage), policy.stock_tick)
    fx_limit = round_up(snapshot.fx.ask * (1 + policy.fx_slippage), policy.fx_tick)
    shares = int(((target - gross) / (stock_limit * fx_limit)).to_integral_value(rounding=ROUND_FLOOR))
    if not 1 <= shares <= policy.max_shares:
        raise AllocationError("share_quantity_out_of_bounds")
    notional = shares * stock_limit
    buy = max(Decimal(0), (notional * (1 + policy.cash_buffer) - usd).to_integral_value(rounding=ROUND_CEILING))
    required = buy * fx_limit
    if required > sgd or required > policy.max_target_sgd:
        raise AllocationError("insufficient_settled_cash")
    return AllocationPlan(shares, stock_limit, fx_limit, notional, buy, required, target)
