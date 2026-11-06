import numpy as np
import pytest
from equity_lab.study.sequence.selection import select_features


def test_selectors_are_fit_only_and_nonempty():
    rng = np.random.default_rng(11)
    x = rng.normal(size=(40, 5, 15)).astype("float32")
    x[:, :, 1] = x[:, :, 0]
    fit = np.arange(20)
    for mode in ["all", "correlation", "kmeans", "som"]:
        first = select_features(x, fit, mode)
        x[20:] *= 100
        assert first == select_features(x, fit, mode)
        assert first and len(first) == len(set(first))
    assert 1 not in select_features(x, fit, "correlation")


def test_shared_encoder_dispatch():
    torch = pytest.importorskip("torch")
    from equity_lab.models.sequence.shared import SharedEncoderMoE

    model = SharedEncoderMoE(features=10, lookback=20)
    out = model(torch.randn(4, 20, 10))
    assert out["logits"].shape == (4,)
    assert sum(out["processed"]) == 8
