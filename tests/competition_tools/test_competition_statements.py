"""Synthetic reviewed statement contracts; no broker fixtures."""

from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest
from competition_tools.crypto_evidence import digest

NOW = datetime(2026, 11, 7, 15, tzinfo=timezone.utc)
DECLARATION = "d" * 64


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / "reviewed-export.txt"
    source.write_text("Synthetic daily statement and calendar, not broker data.")
    raw = dict(
        schema="competition.statement_bundle.v1",
        declaration_sha256=DECLARATION,
        account_ref="synthetic-account",
        base_currency="USD",
        rate_unit="fraction",
        reviewed_by="synthetic-reviewer",
        sources=[dict(id="export", path=source.name, sha256=digest(source))],
        calendar=dict(
            id="synthetic-global",
            status="unconfirmed",
            full_period=True,
            period_start="2026-10-25T16:00:00Z",
            period_end="2027-01-26T22:00:00Z",
            source_ids=["export"],
            sessions=[
                dict(
                    session_date=f"2026-10-{day}",
                    opens_at=f"2026-10-{day}T13:30:00Z",
                    closes_at=f"2026-10-{day}T20:00:00Z",
                )
                for day in [26, 27]
            ],
        ),
        definitions={
            key: dict(
                status="unconfirmed",
                description="Synthetic reviewed definition",
                source_ids=["export"],
            )
            for key in ["position_rate", "turnover_rate", "flat_day"]
        },
        days=[
            dict(
                session_date="2026-10-26",
                complete_day=True,
                position_rate="0.55",
                turnover_rate="0",
                had_any_position=True,
                had_any_trade=False,
                covered_through="2026-10-26T20:00:00Z",
                available_at="2026-10-27T01:00:00Z",
                source_ids=["export"],
            )
        ],
    )
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(raw))
    return path, raw


def load(bundle, raw=None):
    from competition_tools.competition_review.statements import load_statement_bundle

    path, original = bundle
    path.write_text(json.dumps(original if raw is None else raw))
    return load_statement_bundle(path, NOW, declaration_sha256=DECLARATION)


def test_reviewed_statement_missing_days_stay_unknown(bundle):
    result = load(bundle)
    assert result["summary"]["known_position_days"] == 1
    assert result["summary"]["eligibility_under_inputs"] == "unknown"
    assert result["daily_coverage"][1]["flat_day"] is None
    assert result["summary"]["official_eligibility"] == "unverified"


def test_complete_statement_position_or_turnover_paths(bundle):
    raw = deepcopy(bundle[1])
    second = deepcopy(raw["days"][0])
    second.update(
        session_date="2026-10-27",
        covered_through="2026-10-27T20:00:00Z",
        available_at="2026-10-28T01:00:00Z",
    )
    raw["days"].append(second)
    assert load(bundle, raw)["summary"]["path_a_under_inputs"] == "met"
    for row in raw["days"]:
        row.update(position_rate="0", turnover_rate="1", had_any_trade=True)
    result = load(bundle, raw)
    assert result["summary"]["path_b_under_inputs"] == "met"
    assert result["summary"]["known_flat_days"] == 0
    raw["days"][0]["complete_day"] = False
    assert load(bundle, raw)["summary"]["eligibility_under_inputs"] == "unknown"


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "outside",
        "future",
        "partial_close",
        "mixed_currency",
        "mixed_account",
        "bad_unit",
        "unbound",
        "escape",
        "hash",
        "calendar_incomplete",
        "future_calendar_fact",
    ],
)
def test_invalid_bundle_rejected(bundle, mutation):
    raw = deepcopy(bundle[1])
    if mutation == "duplicate":
        raw["days"].append(deepcopy(raw["days"][0]))
    if mutation == "outside":
        raw["days"][0]["session_date"] = "2026-10-28"
    if mutation == "future":
        raw["days"][0]["available_at"] = "2026-11-08T00:00:00Z"
    if mutation == "partial_close":
        raw["days"][0]["covered_through"] = "2026-10-26T15:00:00Z"
    if mutation == "mixed_currency":
        raw["days"][0]["base_currency"] = "HKD"
    if mutation == "mixed_account":
        raw["days"][0]["account_ref"] = "another"
    if mutation == "bad_unit":
        raw["rate_unit"] = "percent"
    if mutation == "unbound":
        raw["declaration_sha256"] = "e" * 64
    if mutation == "escape":
        raw["sources"][0]["path"] = "../reviewed-export.txt"
    if mutation == "hash":
        raw["sources"][0]["sha256"] = "a" * 64
    if mutation == "calendar_incomplete":
        raw["calendar"]["full_period"] = False
    if mutation == "future_calendar_fact":
        raw["calendar"]["sessions"][0].update(
            opens_at="2026-11-08T13:00:00Z", closes_at="2026-11-08T20:00:00Z"
        )
    with pytest.raises(ValueError):
        load(bundle, raw)


def test_cli_consumes_bundle_and_writes_sealed_dynamic_report(
    bundle, tmp_path, monkeypatch
):
    from competition_tools.competition_review import cli
    from competition_tools.crypto_evidence import verify_seal, read_json

    declaration = tmp_path / "declaration"
    declaration.mkdir()
    files = []
    for name in ["declaration.json", "declaration.md", "declaration.zh-CN.md"]:
        p = declaration / name
        p.write_text("{}")
        files.append(dict(path=name, sha256=digest(p)))
    (declaration / "receipt.json").write_text(json.dumps(dict(files=files)))
    raw = deepcopy(bundle[1])
    raw["declaration_sha256"] = digest(declaration / "declaration.json")
    bundle[0].write_text(json.dumps(raw))
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    monkeypatch.setattr(
        cli,
        "calendar_scenario",
        lambda name, now: dict(
            calendar=name, elapsed_sessions=["2026-10-26"], remaining_sessions=[]
        ),
    )
    output = tmp_path / "output"
    cli.audit(declaration, snapshots, output, NOW, statement_bundle=bundle[0])
    report = read_json(output / "audit.json")
    assert report["reviewed_statement"]["summary"]["known_position_days"] == 1
    assert (
        report["reviewed_statement"]["summary"]["official_eligibility"] == "unverified"
    )
    assert verify_seal(output)
    assert (output / "report.md").exists()
    with pytest.raises(FileExistsError):
        cli.audit(declaration, snapshots, output, NOW, statement_bundle=bundle[0])


def test_leveraged_statement_disables_unlevered_planning(bundle):
    raw = deepcopy(bundle[1])
    raw["days"][0]["position_rate"] = "1.2"
    assert (
        load(bundle, raw)["position_planning"]["status"]
        == "unsupported_leveraged_planning"
    )


def test_unknown_source_duplicate_calendar_and_nonfinite_rates_rejected(bundle):
    for field in ["source", "calendar", "rate"]:
        raw = deepcopy(bundle[1])
        if field == "source":
            raw["days"][0]["source_ids"] = ["missing"]
        if field == "calendar":
            raw["calendar"]["sessions"].append(
                deepcopy(raw["calendar"]["sessions"][-1])
            )
        if field == "rate":
            raw["days"][0]["position_rate"] = "NaN"
        with pytest.raises(ValueError):
            load(bundle, raw)


def test_cli_policy_arguments_must_be_paired(tmp_path):
    from competition_tools.competition_review.cli import audit

    with pytest.raises(ValueError, match="REQUIRED_TOGETHER"):
        audit(
            tmp_path,
            tmp_path,
            tmp_path / "out",
            NOW,
            policy_file=tmp_path / "policy.json",
        )
    assert not (tmp_path / "out").exists()
