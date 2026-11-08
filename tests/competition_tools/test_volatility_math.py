"""Independent synthetic sizing/funding/path checks, no account inputs."""

from datetime import datetime, timedelta, timezone
import pytest


def points(prices=(100, 80, 90), targets=None):
    targets = targets or [0.5] * len(prices)
    start = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    return [
        dict(
            at=(start + timedelta(days=i)).isoformat(),
            signal_at=(start + timedelta(days=i, hours=-17)).isoformat(),
            price=p,
            target=w,
            rebalance=i == 0,
        )
        for i, (p, w) in enumerate(zip(prices, targets))
    ]


def test_sample_vol_target_uses_exact_trailing_returns_and_caps():
    from competition_tools.competition_review.volatility_math import target_from_closes

    # returns: .1,-.1; sample SD=sqrt(.02), annualizer=2.
    r = target_from_closes([100, 110, 99], 2, 0.1, 1, 2)
    assert r["estimated_volatility"] == pytest.approx(0.2)
    assert r["weight"] == pytest.approx(0.5)
    assert target_from_closes([100, 110, 99], 2, 0.4, 1, 2)["weight"] == 1
    assert target_from_closes([1, 100, 110, 99], 2, 0.1, 1, 2) == r


@pytest.mark.parametrize(
    "prices", [[100, 100, 100], [100, 101], [100, float("nan"), 101], [100, -1, 101]]
)
def test_missing_zero_or_invalid_vol_blocks(prices):
    from competition_tools.competition_review.volatility_math import target_from_closes

    with pytest.raises(ValueError):
        target_from_closes(prices, 2, 0.1, 1, 252)


def test_self_financing_buy_sell_and_full_allocation():
    from competition_tools.competition_review.volatility_math import rebalance

    stock, cash, cost = rebalance(0, 1, 1, 10)
    assert cash == pytest.approx(0, abs=1e-12)
    assert stock == pytest.approx(1 / 1.001)
    assert stock + cost == pytest.approx(1)
    stock, cash, cost = rebalance(0.6, 0.4, 0.2, 10)
    assert stock / (stock + cash) == pytest.approx(0.2)
    assert stock + cash + cost == pytest.approx(1)
    assert cost == pytest.approx(0.001 * 0.4 / (1 - 0.001 * 0.2))


def test_hold_units_initial_loss_and_terminal_fee_are_included():
    from competition_tools.competition_review.volatility_math import simulate

    r = simulate(points(), 0)
    assert [p["nav"] for p in r["path"]] == pytest.approx([1, 0.9, 0.95])
    assert r["metrics"]["maximum_drawdown"] == pytest.approx(-0.1)
    assert r["metrics"]["total_return"] == pytest.approx(-0.05)
    assert r["path"][1]["exposure"] != pytest.approx(0.5)
    assert r["path"][-1]["stock_value"] == 0
    flat = simulate(points((100, 100, 100)), 10)
    bought = 0.5 / (1 + 0.001 * 0.5)
    cost0 = 0.001 * 0.5 / (1 + 0.001 * 0.5)
    assert flat["metrics"]["total_return"] == pytest.approx(-cost0 - 0.001 * bought)
    assert flat["metrics"]["maximum_drawdown"] == pytest.approx(
        flat["metrics"]["total_return"]
    )


def test_monthly_flag_and_buffer_control_changes_not_daily_resets():
    from competition_tools.competition_review.volatility_math import simulate

    p = points((100, 100, 100, 100), [0.5, 0.7, 0.52, 0.52])
    p[2]["rebalance"] = True
    assert len(simulate(p, 0)["transactions"]) == 3  # entry, scheduled change, terminal
    assert len(simulate(p, 0, buffer=0.05)["transactions"]) == 2


def test_mean_exposure_match_is_explicit_hindsight_with_small_residual():
    from competition_tools.competition_review.volatility_math import (
        simulate,
        match_fixed,
    )

    p = points((100, 80, 90, 110), [0.3, 0.3, 0.6, 0.6])
    p[2]["rebalance"] = True
    mean = simulate(p, 10)["metrics"]["mean_exposure"]
    r = match_fixed(p, 10, mean)
    assert abs(r["residual"]) < 1e-7
    assert r["hindsight_nontradable"] is True
    assert r["result"]["metrics"]["mean_exposure"] == pytest.approx(mean, abs=1e-7)


@pytest.mark.parametrize(
    "mode", ["future_signal", "unordered", "bad_price", "bad_weight", "bad_cost"]
)
def test_invalid_book_inputs_fail(mode):
    from competition_tools.competition_review.volatility_math import simulate

    p = points()
    bps = 10
    if mode == "future_signal":
        p[0]["signal_at"] = p[1]["at"]
    elif mode == "unordered":
        p[1]["at"] = p[0]["at"]
    elif mode == "bad_price":
        p[1]["price"] = 0
    elif mode == "bad_weight":
        p[0]["target"] = 1.1
    elif mode == "bad_cost":
        bps = -1
    with pytest.raises(ValueError):
        simulate(p, bps)
