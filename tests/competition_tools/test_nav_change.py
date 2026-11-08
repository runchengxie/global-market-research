"""Reported NAV components are not a pure price/FX attribution."""

from decimal import Decimal
import pytest
from test_strategy_case import RAW

pytest_plugins = ["test_strategy_case"]

CHANGE = b'<ChangeInNAV accountId="SYNTH" currency="USD" fromDate="20261106" toDate="20261106" startingValue="95" endingValue="100" mtm="6" commissions="-1" interest="0" changeInInterestAccruals="0" netFxTrading="0" fxTranslation="0" realized="0" changeInUnrealized="0" twr="5.26"/>'


def raw(change=CHANGE):
    return RAW.replace(b"</FlexStatement>", change + b"</FlexStatement>")


def explain(value):
    from competition_tools.competition_review.nav_change import explain_nav

    return explain_nav(value, expected_account="SYNTH", base_currency="USD")


def test_exact_reported_components_and_visible_semantic_limit():
    r = explain(raw())
    assert r["status"] == "reconciled_reported_components"
    assert Decimal(r["nav_change"]) == 5
    assert Decimal(r["reported_component_sum"]) == 5
    assert Decimal(r["residual"]) == 0
    assert r["reported_components"]["mtm"] == "6"
    assert r["pure_security_price_fx_attribution_verified"] is False
    assert r["reported_twr_raw"] == "5.26"
    assert r["execution_authorized"] is False


@pytest.mark.parametrize(
    "change",
    [
        CHANGE.replace(b'mtm="6"', b'mtm="7"'),
        CHANGE.replace(b'mtm="6"', b'mtm="6" unknownAdjustment="1"'),
        CHANGE.replace(b'realized="0"', b'realized="4"'),
        CHANGE.replace(b' mtm="6"', b""),
        CHANGE.replace(b'currency="USD"', b'currency="EUR"'),
        CHANGE.replace(b'fromDate="20261106"', b'fromDate="20261105"'),
        CHANGE.replace(b'commissions="-1"', b'commissions="NaN"'),
        CHANGE.replace(b'accountId="SYNTH"', b'accountId="other"'),
        CHANGE.replace(b'currency="USD"', b'currency="USD" model="other"'),
    ],
)
def test_unreconciled_or_unsupported_rows_fail(change):
    with pytest.raises(ValueError):
        explain(raw(change))


def test_conflicting_rows_fail_and_identical_duplicates_not_added():
    r = explain(raw(CHANGE + CHANGE))
    assert Decimal(r["nav_change"]) == 5
    with pytest.raises(ValueError):
        explain(raw(CHANGE + CHANGE.replace(b'mtm="6"', b'mtm="5"')))


def test_bundle_must_match_recomputed_snapshot_and_remain_immutable(case, tmp_path):
    from competition_tools.competition_review.nav_change import explain_bundle
    from competition_tools.crypto_evidence import read_json, seal, digest, verify_seal

    root = tmp_path / "snapshot"
    (root / "report.xml").write_bytes(raw())
    receipt = read_json(root / "receipt.json")
    receipt["report_sha256"] = digest(root / "report.xml")
    import json

    (root / "receipt.json").write_text(json.dumps(receipt))
    (root / "seal.json").unlink()
    seal(root)
    out = tmp_path / "bridge"
    explain_bundle(root, out)
    verify_seal(out)
    with pytest.raises(FileExistsError):
        explain_bundle(root, out)
    (root / "report.xml").write_bytes(
        raw(
            CHANGE.replace(b'endingValue="100"', b'endingValue="101"').replace(
                b'mtm="6"', b'mtm="7"'
            )
        )
    )
    receipt["report_sha256"] = digest(root / "report.xml")
    (root / "receipt.json").write_text(json.dumps(receipt))
    (root / "seal.json").unlink()
    seal(root)
    with pytest.raises(ValueError):
        explain_bundle(root, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
