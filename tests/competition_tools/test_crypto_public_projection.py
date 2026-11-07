import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location(
    "crypto_public",
    Path(__file__).resolve().parents[2] / "scripts/crypto_public_projection.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_current_guides_do_not_claim_public_results_are_synthetic_only():
    root = Path(__file__).resolve().parents[2]
    for suffix in ["", ".zh-CN"]:
        text = (root / f"docs/research/sequence-diagnostics{suffix}.md").read_text()
        assert "synthetic examples only" not in text
        assert "只展示合成示例" not in text


def test_public_contract_rejects_private_or_individual_rows():
    for value in [
        {"schema": "crypto.research_public.v1", "raw_prices": [1, 2]},
        {"path": "/private/account.json"},
        {"schema": "crypto.research_public.v1", "predictions": [0.1]},
    ]:
        with pytest.raises(ValueError):
            module.validate_public(value)


def test_published_fixture_matches_projection_code_and_closed_contract():
    import json

    root = Path(__file__).resolve().parents[2]
    value = json.loads((root / "site/src/data/crypto-evidence.v1.json").read_text())
    assert module.validate_public(value) == value
    assert value["sources"]["projection_code"] == module.projection_code_hash()
    for mutate in [
        lambda d: d["rows"][0].update({"account_path": "/private/account"}),
        lambda d: d["experiment"].update({"fit_count": 25}),
        lambda d: d["operations"].update({"health_status": "unknown_ready"}),
    ]:
        changed = json.loads(json.dumps(value))
        mutate(changed)
        with pytest.raises(ValueError):
            module.validate_public(changed)
