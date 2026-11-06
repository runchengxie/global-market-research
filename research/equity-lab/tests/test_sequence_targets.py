import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("exchange_calendars")
from equity_lab.models.sequence.objectives import (
    target_transform,
    encode_targets,
    decode_scores,
)  # noqa:E402
from equity_lab.study.sequence.target_fit import fit_target, score_saved  # noqa:E402


def test_fit_only_transform_and_return_units():
    values = np.array([0.01, 0.03, 90.0])
    transform = target_transform("regression", values, [0, 1])
    assert transform["center"] == pytest.approx(0.02)
    assert transform["scale"] == pytest.approx(0.01)
    encoded = encode_targets(values, transform)
    assert encoded[:2] == pytest.approx([-1, 1])
    assert decode_scores(encoded, transform) == pytest.approx(values)
    changed = values.copy()
    changed[2] = -80
    assert target_transform("regression", changed, [0, 1]) == transform
    constant = target_transform("regression", np.zeros(3), [0, 1])
    assert constant["scale"] == 1e-6
    binary = target_transform("classification", np.array([0, 1, 0]), [0, 1])
    assert decode_scores(np.array([0.0]), binary)[0] == 0.5
    with pytest.raises(ValueError):
        target_transform("classification", values, [0, 1])


@pytest.mark.parametrize("objective", ["classification", "regression"])
@pytest.mark.parametrize("name", ["prior", "linear", "matched", "equal", "sparse"])
def test_saved_target_scores_reconstruct(tmp_path, objective, name):
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.protocol import make_folds
    import time

    samples = build_samples(snapshot_fixture(tmp_path), 5)
    fold = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)[0]
    path = tmp_path / "fit"
    path.mkdir()
    result = fit_target(
        name,
        objective,
        samples,
        fold,
        11,
        dict(epochs=1, batch_size=128, patience=5),
        path,
        time.monotonic() + 60,
    )
    assert np.allclose(
        score_saved(path, samples.x[fold.test]), result["test"], atol=1e-8, rtol=0
    )
    assert np.isfinite(result["validation"]).all()
    if objective == "classification":
        assert ((result["test"] >= 0) & (result["test"] <= 1)).all()
