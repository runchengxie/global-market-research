import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/crypto_followup_projection.py"


def module():
    spec = importlib.util.spec_from_file_location("crypto_followup_projection", SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_closed_public_result_and_incomplete_runs():
    m = module()
    with pytest.raises(ValueError, match="INCOMPLETE"):
        m.validate_comparison(dict(status="partial"))
    with pytest.raises(ValueError, match="FIELDS"):
        m.validate_public(
            dict(schema="crypto.followup_public.v1", private_config="secret")
        )


def test_public_fixture_matches_source_and_no_private_fields():
    m = module()
    fixture = SCRIPT.parent.parent / "site/src/data/crypto-followup.v1.json"
    if not fixture.exists():
        pytest.skip("real export not produced yet")
    import json
    import hashlib

    data = json.loads(fixture.read_text())
    m.validate_public(data)
    assert (
        data["sources"]["projection_code"]
        == hashlib.sha256(SCRIPT.read_text().replace("\r\n", "\n").encode()).hexdigest()
    )
    text = fixture.read_text()
    assert (
        "/run/media/" not in text
        and "producer_python" not in text
        and "prediction" not in data["forward"]
    )


def test_public_semantics_reject_path_and_unknown_aggregate():
    import json
    from copy import deepcopy

    data = json.loads(
        (SCRIPT.parent.parent / "site/src/data/crypto-followup.v1.json").read_text()
    )
    for mutate in [
        lambda x: x["forward"].update(prefix_head="/private"),
        lambda x: x["comparison"]["aggregates"][0].update(kind="/private"),
        lambda x: x["comparison"]["gates"][0].update(entropy=-1),
        lambda x: x["diagnostics"]["rows"][0].update(count="private"),
    ]:
        bad = deepcopy(data)
        mutate(bad)
        with pytest.raises(ValueError):
            module().validate_public(bad)
