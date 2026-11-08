from decimal import Decimal
import pytest


def marks(values, days=None):
    days = days or [1, 2, 5][: len(values)]
    return [
        dict(endpoint=f"2026-01-{d:02d}T14:30:00+00:00", base_values={"a": str(v)})
        for d, v in zip(days, values)
    ]


def test_initial_loss_drawdown_and_constant_units():
    from competition_tools.competition_review.etf_paths import path_metrics

    r = path_metrics({"a": ".5"}, {"a": ".5"}, marks([100, 80, 90]), "0", "0")
    assert [Decimal(x["nav"]) for x in r["path"]] == [
        Decimal(1),
        Decimal(".9"),
        Decimal(".95"),
    ]
    assert Decimal(r["maximum_drawdown"]) == Decimal("-.1")
    assert Decimal(r["return_after_initial_cost"]) == Decimal("-.05")


def test_fee_is_initial_drawdown_cash_off_and_calendar_accrual():
    from competition_tools.competition_review.etf_paths import path_metrics

    r = path_metrics({"a": ".5"}, {}, marks([100, 100], [1, 5]), "10", ".04")
    assert Decimal(r["path"][0]["drawdown"]) == Decimal("-.0005")
    expected = Decimal(".9995") * (1 + Decimal(".04") * 4 / 365)
    assert abs(Decimal(r["path"][-1]["nav"]) - expected) < Decimal("1e-25")
    assert Decimal(r["initial_stock_turnover"]) == Decimal(".5")


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "duplicate",
        "negative",
        "nan",
        "unfunded",
        "leveraged",
        "foreign_asset",
    ],
)
def test_invalid_path_or_budget_fails(mode):
    from competition_tools.competition_review.etf_paths import path_metrics

    rows = marks([100, 101])
    weights = {"a": ".5"}
    if mode == "missing":
        rows[1]["base_values"] = {}
    elif mode == "duplicate":
        rows[1]["endpoint"] = rows[0]["endpoint"]
    elif mode == "negative":
        rows[1]["base_values"]["a"] = "-1"
    elif mode == "nan":
        rows[1]["base_values"]["a"] = "NaN"
    elif mode == "unfunded":
        weights = {"a": "1"}
    elif mode == "leveraged":
        weights = {"a": "1.1"}
    elif mode == "foreign_asset":
        weights = {"other": ".5"}
    with pytest.raises(ValueError):
        path_metrics({"a": ".5"}, weights, rows, "10", "0")
