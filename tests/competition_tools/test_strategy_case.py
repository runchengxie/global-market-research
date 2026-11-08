"""File-backed synthetic evidence; no account or performance claims."""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from competition_tools.crypto_evidence import digest, seal

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)
STAMP = "2026-11-07T00:00:00Z"
RAW = b"""<FlexQueryResponse type="AF"><FlexStatements><FlexStatement accountId="SYNTH" fromDate="20261106" toDate="20261106"><AccountInformation accountId="SYNTH" currency="USD"/><OpenPositions><OpenPosition accountId="SYNTH" currency="USD" assetCategory="STK" symbol="A" conid="1" reportDate="20261106" position="50" markPrice="1" positionValue="50" multiplier="1" fxRateToBase="1" levelOfDetail="SUMMARY"/></OpenPositions><EquitySummaryInBase><EquitySummaryByReportDateInBase accountId="SYNTH" currency="USD" reportDate="20261106" total="100" stock="50" stockLong="50" stockShort="0" cash="50" interestAccruals="0" dividendAccruals="0"/></EquitySummaryInBase><CashReport><CashReportCurrency accountId="SYNTH" currency="USD" levelOfDetail="Currency" fromDate="20261106" toDate="20261106" endingCash="50"/></CashReport></FlexStatement></FlexStatements></FlexQueryResponse>"""


def write(path, value):
    path.write_text(json.dumps(value))
    return digest(path)


@pytest.fixture
def case(tmp_path):
    from competition_tools.competition_review.flex_reconciliation import (
        reconcile_snapshot,
    )

    declaration = tmp_path / "declaration"
    declaration.mkdir()
    records = []
    for name in ["declaration.json", "declaration.md", "declaration.zh-CN.md"]:
        records.append(dict(path=name, sha256=write(declaration / name, {})))
    write(declaration / "receipt.json", dict(files=records))
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "report.xml").write_bytes(RAW)
    write(
        snapshot / "snapshot.json",
        reconcile_snapshot(
            RAW, expected_account="SYNTH", base_currency="USD", account_ref="paper"
        ),
    )
    write(
        snapshot / "receipt.json",
        dict(
            status="collected",
            account_ref="paper",
            report_sha256=digest(snapshot / "report.xml"),
            finished_at=STAMP,
        ),
    )
    seal(snapshot)
    policy = dict(
        status="confirmed",
        confirmed_by="synthetic-reviewer",
        benchmark="SYNTHETIC",
        declaration_sha256=digest(declaration / "declaration.json"),
        model_sha256="",
        effective_at=STAMP,
        confirmed_at=STAMP,
        account_ref="paper",
        top_k=2,
        entry_buffer=1,
        exit_buffer=1,
        name_cap="0.8",
        gross_cap="1",
        turnover_cap="0.5",
        drift_band="0.3",
        max_age_hours=100,
    )
    paths = {
        k: tmp_path / (k + ".json")
        for k in ["policy", "pit", "universe", "model", "scores", "target"]
    }
    payloads = dict(
        pit={},
        model={},
        universe=dict(symbols=["1"]),
        scores=dict(scores={"1": "-0.2"}),
        target=dict(weights={"1": "0.6"}),
    )
    refs = {}
    for k, data in payloads.items():
        refs[k] = dict(
            path=str(paths[k]),
            sha256=write(paths[k], data),
            effective_at=STAMP,
            available_at=STAMP,
        )
    policy["model_sha256"] = refs["model"]["sha256"]
    refs["policy"] = dict(
        path=str(paths["policy"]),
        sha256=write(paths["policy"], policy),
        effective_at=STAMP,
        available_at=STAMP,
    )
    refs["scores"]["parents"] = {
        k: refs[k]["sha256"] for k in ["pit", "universe", "model"]
    }
    refs["target"]["parents"] = dict(scores=refs["scores"]["sha256"])
    manifest = dict(
        schema="competition.strategy_case.v1",
        declaration_root=str(declaration),
        snapshot_root=str(snapshot),
        sources=refs,
        cost_bps="10",
    )
    path = tmp_path / "case.json"
    write(path, manifest)
    return path, manifest, paths


def build(case):
    from competition_tools.competition_review.strategy_case import build_case

    return build_case(case, NOW)


def test_complete_chain_reads_actual_weights_and_compares_exact_arithmetic(case):
    path, _, _ = case
    r = build(path)
    assert r["daily_review"]["status"] == "maintain_candidate"
    assert r["current_weights"] == {"1": "0.5"}
    assert r["comparison"]["target"]["gross_weight"] == "0.6"
    assert Decimal(r["comparison"]["two_way_turnover"]) == Decimal("0.1")
    assert Decimal(r["comparison"]["linear_cost_fraction"]) == Decimal("0.0001")
    assert r["execution_authorized"] is False
    assert r["model_semantics_verified"] is False


def test_missing_sources_preserve_observations_without_comparison(case):
    path, manifest, _ = case
    manifest["sources"] = {}
    write(path, manifest)
    r = build(path)
    assert r["daily_review"]["status"] == "blocked"
    assert set(r["missing_roles"]) == {
        "policy",
        "pit",
        "universe",
        "model",
        "scores",
        "target",
    }
    assert r["comparison"] is None
    assert r["current_weights"] == {"1": "0.5"}


@pytest.mark.parametrize(
    "mode",
    [
        "tamper",
        "future_source",
        "future_policy",
        "future_receipt",
        "bad_parent",
        "bad_universe",
        "unscored_target",
        "negative_weight",
        "nonfinite_score",
        "tamper_snapshot",
    ],
)
def test_inconsistent_evidence_fails_closed(case, mode):
    path, manifest, paths = case
    if mode == "tamper":
        paths["model"].write_text("changed")
    elif mode == "future_source":
        manifest["sources"]["scores"]["available_at"] = "2026-11-09T00:00:00Z"
    elif mode == "future_policy":
        p = json.loads(paths["policy"].read_text())
        p["confirmed_at"] = "2026-11-09T00:00:00Z"
        manifest["sources"]["policy"]["sha256"] = write(paths["policy"], p)
    elif mode == "future_receipt":
        root = path.parent / "snapshot"
        p = json.loads((root / "receipt.json").read_text())
        p["finished_at"] = "2026-11-09T00:00:00Z"
        write(root / "receipt.json", p)
        (root / "seal.json").unlink()
        seal(root)
    elif mode == "bad_parent":
        manifest["sources"]["target"]["parents"] = {"scores": "a" * 64}
    elif mode == "tamper_snapshot":
        root = path.parent / "snapshot"
        p = json.loads((root / "snapshot.json").read_text())
        p["stock"]["positions"][0]["observed_weight"] = "0.9"
        write(root / "snapshot.json", p)
        (root / "seal.json").unlink()
        seal(root)
    else:
        role, payload = {
            "bad_universe": ("universe", {"symbols": ["1", "1"]}),
            "unscored_target": ("target", {"weights": {"2": "0.6"}}),
            "negative_weight": ("target", {"weights": {"1": "-0.1"}}),
            "nonfinite_score": ("scores", {"scores": {"1": "NaN"}}),
        }[mode]
        manifest["sources"][role]["sha256"] = write(paths[role], payload)
    write(path, manifest)
    with pytest.raises(ValueError):
        build(path)


def test_cli_writes_fresh_sealed_bilingual_private_output(case, tmp_path):
    from competition_tools.competition_review.strategy_cli import run
    from competition_tools.crypto_evidence import verify_seal

    path, manifest, _ = case
    manifest["sources"] = {}
    write(path, manifest)
    output = tmp_path / "review"
    r = run(path, output, NOW)
    assert r["daily_review"]["status"] == "blocked"
    verify_seal(output)
    assert (output / "report.zh-CN.md").exists()
    assert "not" in (output / "report.md").read_text()
    assert not (output / "targets.json").exists()
    with pytest.raises(FileExistsError):
        run(path, output, NOW)


def test_invalid_case_creates_no_output(case, tmp_path):
    from competition_tools.competition_review.strategy_cli import run

    path, _, paths = case
    paths["model"].write_text("tampered")
    output = tmp_path / "review"
    with pytest.raises(ValueError):
        run(path, output, NOW)
    assert not output.exists()


@pytest.mark.parametrize(
    "mode",
    [
        "missing_confirmation_actor",
        "policy_after_target",
        "stale_account",
        "stale_scores",
    ],
)
def test_prospective_confirmation_and_staleness(case, mode):
    path, manifest, paths = case
    policy = json.loads(paths["policy"].read_text())
    if mode == "missing_confirmation_actor":
        policy.pop("confirmed_by", None)
    elif mode == "policy_after_target":
        policy["confirmed_at"] = "2026-11-07T12:00:00Z"
        manifest["sources"]["policy"]["available_at"] = "2026-11-07T12:00:00Z"
    elif mode == "stale_account":
        policy["max_age_hours"] = 25
    else:
        for role in ["pit", "universe", "model", "scores"]:
            manifest["sources"][role]["effective_at"] = "2026-10-01T00:00:00Z"
            manifest["sources"][role]["available_at"] = "2026-10-01T00:00:00Z"
    manifest["sources"]["policy"]["sha256"] = write(paths["policy"], policy)
    write(path, manifest)
    if mode in {"missing_confirmation_actor", "policy_after_target"}:
        with pytest.raises(ValueError):
            build(path)
    else:
        result = build(path)
        assert result["daily_review"]["status"] == "blocked"
        assert result["comparison"] is None


@pytest.mark.parametrize(
    "mode",
    [
        "model_after_score_effective",
        "score_after_target_effective",
        "policy_after_target_effective",
    ],
)
def test_parents_must_be_available_before_child_effective_time(case, mode):
    path, manifest, _ = case
    if mode == "model_after_score_effective":
        manifest["sources"]["model"]["available_at"] = "2026-11-07T12:00:00Z"
        manifest["sources"]["scores"]["available_at"] = "2026-11-07T13:00:00Z"
        manifest["sources"]["target"]["available_at"] = "2026-11-07T14:00:00Z"
    elif mode == "score_after_target_effective":
        manifest["sources"]["scores"]["available_at"] = "2026-11-07T13:00:00Z"
        manifest["sources"]["target"]["available_at"] = "2026-11-07T14:00:00Z"
    else:
        manifest["sources"]["policy"]["available_at"] = "2026-11-07T12:00:00Z"
    write(path, manifest)
    with pytest.raises(ValueError, match="NONCAUSAL"):
        build(path)


def test_provided_empty_policy_is_invalid_not_missing_evidence(case, tmp_path):
    from competition_tools.competition_review.strategy_cli import run

    path, manifest, paths = case
    manifest["sources"]["policy"]["sha256"] = write(paths["policy"], {})
    write(path, manifest)
    out = tmp_path / "invalid-empty-policy"
    with pytest.raises(ValueError):
        run(path, out, NOW)
    assert not out.exists()
