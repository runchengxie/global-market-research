import pytest

np = pytest.importorskip("numpy")
from crypto_mm.exploration.diagnostics import distribution  # noqa: E402


def test_cash_distribution_uses_fixed_hurdles_not_outcome_selected():
    result = distribution([-0.001, 0, 0.001, 0.003], [0.02, -0.01, 0.001, 0.004])
    assert result["count"] == 4
    assert result["prediction_quantiles"][0] == -0.001
    assert result["above_hurdles"] == [0.5, 0.25, 0.25]
    with pytest.raises(ValueError):
        distribution([float("nan")], [0])


def test_sequence_windows_do_not_cross_assets_and_use_current_row():
    from datetime import datetime, timedelta, timezone
    from crypto_mm.exploration.study import make_windows, split_sample

    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        dict(
            asset=a,
            time=t + timedelta(hours=4 * i),
            exit_time=t + timedelta(hours=4 * i + 8),
            features={"price_only": [i] * 7},
            target=0,
            entry=100,
            exit=100,
        )
        for a in ["BTCUSDT", "ETHUSDT"]
        for i in range(60)
    ]
    x, r = make_windows(rows, 12)
    assert x.shape == (98, 12, 7)
    assert x[0, -1, 0] == 11 and x[1, 0, 0] == 0
    fit, val, test = split_sample(
        r, t + timedelta(days=8), t + timedelta(days=10), validation_days=2
    )
    assert max(r[i]["exit_time"] for i in fit) < min(r[i]["time"] for i in val)
    assert max(r[i]["exit_time"] for i in val) < min(r[i]["time"] for i in test)


def test_parameter_match_and_task_gradient():
    torch = pytest.importorskip("torch")
    from crypto_mm.exploration.models import Model, matched_width

    dense = Model("dense")
    single = Model("matched")

    def count(m):
        return sum(p.numel() for p in m.parameters())

    assert abs(count(dense) - count(single)) / count(dense) < 0.06
    assert matched_width() > 8
    x = torch.randn(4, 12, 7)
    y, g = dense(x)
    y.square().mean().backward()
    assert dense.router.weight.grad.abs().sum() > 0
    assert g.shape == (4, 3)
    equal = Model("equal")
    _, g = equal(x)
    assert torch.allclose(g, torch.ones_like(g) / 3)


def test_validation_selection_and_empty_cash_tie():
    from crypto_mm.exploration.study import select_hurdle

    rows = [
        dict(asset=a, entry=100.0, exit=100.0)
        for a in ["BTCUSDT", "ETHUSDT"]
        for _ in range(3)
    ]
    assert select_hurdle(np.zeros(6), rows) == 0.002
    # Selection accepts only supplied validation rows, no global test results.
    assert select_hurdle(np.ones(6) * 0.0005, rows) == 0.002


def test_exclusive_plan_claim_and_fixed_configuration(tmp_path):
    from crypto_mm.exploration.study import CONFIG, claim_plan
    from crypto_mm.intraday.study import FOLDS
    from crypto_mm.intraday.inputs import write, seal

    plan = tmp_path / "plan"
    plan.mkdir()
    write(
        plan / "plan.json",
        dict(
            schema="crypto.comparison_plan.v1",
            config=CONFIG,
            folds=FOLDS,
            claim=str(tmp_path / "plan.claim"),
        ),
    )
    seal(plan)
    claim_plan(plan / "plan.json")
    with pytest.raises(FileExistsError):
        claim_plan(plan / "plan.json")
