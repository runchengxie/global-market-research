import pytest
import numpy as np

torch = pytest.importorskip("torch")
from equity_lab.models.sequence.lstm import SequenceModel, parameter_matched_width  # noqa: E402
from equity_lab.models.sequence.checkpoint import save_checkpoint, load_checkpoint  # noqa: E402


def test_sparse_dispatch_counts_and_dense_equivalence():
    torch.manual_seed(11)
    model = SequenceModel(features=3, lookback=5, units=4, experts=3, top_k=2)
    x = torch.randn(7, 5, 3)
    out = model(x)
    assert sum(out["processed"]) == 14
    assert (out["weights"] == 0).sum().item() == 7
    assert torch.allclose(out["weights"].sum(1), torch.ones(7))
    dense = torch.stack([e(x)[0].flatten(1) for e in model.experts], dim=1)
    expected = model.head((dense * out["weights"].unsqueeze(-1)).sum(1)).squeeze(-1)
    assert torch.allclose(out["logits"], expected, atol=1e-6)


def test_empty_experts_skipped_and_top_one_task_gradient():
    model = SequenceModel(features=3, lookback=5, units=4, top_k=1)
    with torch.no_grad():
        model.router.weight.zero_()
        model.router.bias.copy_(torch.tensor([2.0, 0.0, -2.0]))
    out = model(torch.randn(8, 5, 3))
    assert out["processed"] == [8, 0, 0]
    out["logits"].sum().backward()
    assert model.router.bias.grad.abs().sum() > 0
    assert next(model.experts[0].parameters()).grad is not None
    assert next(model.experts[1].parameters()).grad is None


def test_parameter_matching_and_checkpoint(tmp_path):
    model = SequenceModel(features=10, lookback=20)
    width = parameter_matched_width(model.config)
    target = sum(p.numel() for p in model.parameters())
    distances = []
    for unit in [width - 1, width, width + 1]:
        single = SequenceModel(features=10, lookback=20, units=unit, experts=1)
        distances.append(abs(sum(p.numel() for p in single.parameters()) - target))
    assert distances[1] == min(distances)
    model.eval()
    x = torch.randn(3, 20, 10)
    save_checkpoint(model, tmp_path / "model.pt", {"features": list(range(10))})
    restored, metadata = load_checkpoint(tmp_path / "model.pt")
    assert torch.equal(model(x)["logits"], restored(x)["logits"])
    assert len(metadata["features"]) == 10


def test_transformer_dispatch_and_shape():
    from equity_lab.models.sequence.transformer import SequenceTransformer

    model = SequenceTransformer(features=10, lookback=60, top_k=2)
    out = model(torch.randn(2, 60, 10))
    assert out["logits"].shape == (2,)
    assert np.isfinite(out["logits"].detach().numpy()).all()
    assert sum(out["processed"]) == 2 * 60 * 2 * 2


def test_original_five_by_fifteen_dense_matches_manual_lstm():
    # Independent recurrence checks full sequence flattening and representation mixing.
    torch.manual_seed(23)
    model = SequenceModel(features=15, lookback=5, units=3, top_k=None)
    x = torch.randn(2, 5, 15)
    paths = []
    for expert in model.experts:
        h = torch.zeros(2, 3)
        c = torch.zeros(2, 3)
        trajectory = []
        for day in range(5):
            gates = (
                x[:, day] @ expert.weight_ih_l0.T
                + h @ expert.weight_hh_l0.T
                + expert.bias_ih_l0
                + expert.bias_hh_l0
            )
            i, f, g, o = gates.chunk(4, dim=-1)
            c = f.sigmoid() * c + i.sigmoid() * g.tanh()
            h = o.sigmoid() * c.tanh()
            trajectory.append(h)
        paths.append(torch.stack(trajectory, dim=1).flatten(1))
    weights = model.router(x[:, -1]).softmax(-1)
    expected = model.head((torch.stack(paths, 1) * weights[:, :, None]).sum(1)).squeeze(
        -1
    )
    assert torch.allclose(model(x)["logits"], expected, atol=1e-6)


def test_dense_transformer_has_single_ffn_per_layer():
    from equity_lab.models.sequence.transformer import SequenceTransformer

    model = SequenceTransformer(top_k=None)
    assert all(len(ffn.experts) == 1 for ffn in model.ffn)


def test_fitted_routing_interventions_hold_weights_fixed():
    model = SequenceModel(features=3, lookback=5, units=4, top_k=None)
    model.eval()
    x = torch.randn(6, 5, 3)
    before = {name: value.clone() for name, value in model.state_dict().items()}
    equal = model(x, intervention="equal")
    assert torch.allclose(equal["weights"], torch.ones(6, 3) / 3)
    removed = model(x, intervention={"drop": 1})
    assert removed["processed"][1] == 0
    assert torch.allclose(removed["weights"].sum(1), torch.ones(6))
    assert all(
        torch.equal(value, before[name]) for name, value in model.state_dict().items()
    )


def test_top_one_dropping_unselected_expert_preserves_prediction():
    model = SequenceModel(features=3, lookback=5, units=4, top_k=1)
    with torch.no_grad():
        model.router.weight.zero_()
        model.router.bias.copy_(torch.tensor([2.0, 0.0, -2.0]))
    x = torch.randn(4, 5, 3)
    assert torch.equal(model(x)["logits"], model(x, intervention={"drop": 1})["logits"])
