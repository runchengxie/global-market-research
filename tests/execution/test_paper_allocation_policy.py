from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from packages.execution_policies.paper_allocation import (
    AllocationError,
    AllocationPolicy,
    Quote,
    Snapshot,
    compute_allocation,
)

NOW = datetime(2026, 11, 6, 15, tzinfo=timezone.utc)


def policy(**changes):
    return replace(
        AllocationPolicy(
            target_weight=D(".5"),
            max_target_sgd=D("20000"),
            max_shares=500,
            reference_close=D("100"),
            reference_date=date(2026, 11, 5),
            stock_tick=D(".05"),
            fx_tick=D(".0001"),
        ),
        **changes,
    )


def snapshot(**changes):
    return replace(
        Snapshot(
            nav_sgd=D("10000"),
            gross_sgd=D("0"),
            sgd_cash=D("10000"),
            usd_cash=D("0"),
            sgd_settled=D("10000"),
            usd_settled=D("0"),
            stock=Quote(D("99.99"), D("100"), NOW, True),
            fx=Quote(D("1.30"), D("1.301"), NOW, True),
        ),
        **changes,
    )


def test_limits_round_up_to_qualified_ticks_and_shares_down():
    plan = compute_allocation(policy(), snapshot(), NOW)
    assert plan.stock_limit == D("100.20")
    assert plan.fx_limit == D("1.3017")
    assert plan.shares == 38
    assert plan.usd_to_buy == D("3827")
    assert plan.sgd_required == D("4981.6059")
    assert plan.target_sgd == D("5000")


def test_existing_settled_usd_avoids_fx_and_policy_changes_quantity():
    plan = compute_allocation(
        policy(target_weight=D(".2")),
        snapshot(
            usd_cash=D("3000"),
            usd_settled=D("3000"),
            sgd_cash=D("0"),
            sgd_settled=D("0"),
        ),
        NOW,
    )
    assert plan.shares == 15
    assert plan.usd_to_buy == 0
    assert plan.sgd_required == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_weight", D("0")),
        ("target_weight", D("1.1")),
        ("max_target_sgd", D("NaN")),
        ("max_shares", True),
        ("stock_tick", D("0")),
        ("stock_slippage", D("Infinity")),
        ("cash_buffer", D("-.01")),
        ("reference_close", D("-1")),
    ],
)
def test_invalid_policy_cannot_produce_plan(field, value):
    with pytest.raises(AllocationError):
        compute_allocation(policy(**{field: value}), snapshot(), NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("nav_sgd", D("NaN")),
        ("nav_sgd", D("0")),
        ("usd_cash", D("-1")),
        ("gross_sgd", D("5000")),
        ("sgd_settled", D("1")),
        ("usd_cash", True),
        ("account_currency", "USD"),
        ("stock_currency", "SGD"),
    ],
)
def test_unsafe_snapshot_blocks_allocation(field, value):
    with pytest.raises(AllocationError):
        compute_allocation(policy(), snapshot(**{field: value}), NOW)


@pytest.mark.parametrize(
    "quote",
    [
        Quote(D("101"), D("100"), NOW, True),
        Quote(D("90"), D("100"), NOW, True),
        Quote(D("99.9"), D("100"), NOW, False),
        Quote(D("99.9"), D("100"), NOW - timedelta(seconds=16), True),
        Quote(D("99.9"), D("100"), NOW + timedelta(seconds=2), True),
        Quote(D("99.9"), D("100"), NOW.replace(tzinfo=None), True),
        Quote(D("NaN"), D("100"), NOW, True),
    ],
)
def test_unusable_quotes_fail_closed(quote):
    with pytest.raises(AllocationError):
        compute_allocation(policy(), snapshot(stock=quote), NOW)


def test_reference_and_current_clock_must_be_valid():
    with pytest.raises(AllocationError):
        compute_allocation(policy(reference_close=D("90")), snapshot(), NOW)
    with pytest.raises(AllocationError):
        compute_allocation(policy(reference_date=NOW.date()), snapshot(), NOW)
    with pytest.raises(AllocationError):
        compute_allocation(policy(), snapshot(), NOW.replace(tzinfo=None))
