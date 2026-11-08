"""Verify file identity and attributed lineage before private weight comparisons."""

from datetime import date, datetime, timezone
from decimal import Decimal, DecimalException
from pathlib import Path

from competition_tools.crypto_evidence import digest, read_json, verify_seal
from competition_tools.datasets.daily_storage import safe_path
from .decision import review_decision
from .evidence import aware
from .flex_reports import discover_report
from .flex_reconciliation import reconcile_snapshot
from .participation import decimal

ROLES = ("policy", "pit", "universe", "model", "scores", "target")


def _hash(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("INVALID_CASE_HASH")
    return value


def _path(value, base):
    p = Path(value)
    return safe_path(p if p.is_absolute() else base / p)


def _declaration(root):
    receipt = read_json(root / "receipt.json")
    files = receipt["files"]
    names = {"declaration.json", "declaration.md", "declaration.zh-CN.md"}
    if len(files) != 3 or {r["path"] for r in files} != names:
        raise ValueError("INVALID_DECLARATION_RECEIPT")
    for r in files:
        if digest(safe_path(root / r["path"])) != _hash(r["sha256"]):
            raise ValueError("DECLARATION_RECEIPT_MISMATCH")
    return digest(root / "declaration.json")


def _snapshot(root, decision_time):
    verify_seal(root)
    receipt = read_json(root / "receipt.json")
    snapshot = read_json(root / "snapshot.json")
    available = aware(receipt["finished_at"])
    if available > decision_time or receipt["status"] != "collected":
        raise ValueError("SNAPSHOT_UNAVAILABLE")
    if digest(root / "report.xml") != receipt["report_sha256"]:
        raise ValueError("SNAPSHOT_REPORT_HASH_MISMATCH")
    raw = (root / "report.xml").read_bytes()
    accounts = discover_report(raw)["accounts"]
    if len(accounts) != 1 or snapshot["account_ref"] != receipt["account_ref"]:
        raise ValueError("SNAPSHOT_ACCOUNT_MISMATCH")
    derived = reconcile_snapshot(
        raw,
        expected_account=accounts[0],
        base_currency=snapshot["base_currency"],
        account_ref=receipt["account_ref"],
    )
    if derived != snapshot or derived["status"] != "reconciled_stock_cash":
        raise ValueError("SNAPSHOT_NOT_REPRODUCIBLE_OR_RECONCILED")
    effective = datetime.combine(
        date.fromisoformat(snapshot["report_date"]), datetime.min.time(), timezone.utc
    )
    if effective > available:
        raise ValueError("SNAPSHOT_NONCAUSAL_DATE")
    weights = {}
    for p in snapshot["stock"]["positions"]:
        key = p["conid"]
        if (
            not isinstance(key, str)
            or not key.isascii()
            or not key.isdigit()
            or int(key) <= 0
            or key in weights
        ):
            raise ValueError("INVALID_POSITION_IDENTITY")
        weights[key] = str(decimal(p["observed_weight"]))
    if not weights:
        raise ValueError("EMPTY_OBSERVED_WEIGHTS")
    return (
        snapshot,
        weights,
        dict(
            sha256=digest(root / "snapshot.json"),
            effective_at=effective.isoformat(),
            available_at=available.isoformat(),
        ),
    )


def _scores(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("INVALID_SCORES")
    for k, v in value.items():
        if not isinstance(k, str) or not k or type(v) not in (str, int, float):
            raise ValueError("INVALID_SCORE")
        if not Decimal(str(v)).is_finite():
            raise ValueError("INVALID_SCORE")
    return value


def _weights(value):
    if (
        not isinstance(value, dict)
        or not value
        or any(not isinstance(k, str) or not k for k in value)
    ):
        raise ValueError("INVALID_WEIGHTS")
    return {k: str(decimal(v)) for k, v in value.items()}


def compare_weights(current, target, cost_bps):
    """Static arithmetic only; stock shock holds cash/FX/accrual values constant."""
    current = {k: decimal(v) for k, v in current.items()}
    target = {k: decimal(v) for k, v in target.items()}
    cost = decimal(cost_bps)
    if cost > 10000:
        raise ValueError("INVALID_COST_BPS")
    turnover = sum(
        (
            abs(current.get(k, 0) - target.get(k, 0))
            for k in current.keys() | target.keys()
        ),
        Decimal(0),
    )

    def describe(weights):
        gross = sum(weights.values(), Decimal(0))
        return dict(
            gross_weight=str(gross),
            largest_name_weight=str(max(weights.values(), default=Decimal(0))),
            non_stock_residual=str(1 - gross),
            proportional_stock_shocks={
                str(shock): str(gross * shock)
                for shock in [Decimal("-0.2"), Decimal("-0.1"), Decimal("0.1")]
            },
        )

    return dict(
        scope="static_weight_and_linear_cost_scenarios_not_backtest_or_forecast",
        current=describe(current),
        target=describe(target),
        two_way_turnover=str(turnover),
        one_way_cost_bps=str(cost),
        linear_cost_fraction=str(turnover * cost / 10000),
        assumptions=[
            "All stock base-currency values change by the same supplied shock; cash, FX and accruals held constant.",
            "Linear cost applies to each absolute stock weight change; excludes FX conversion, taxes, nonlinear impact and financing.",
            "Non-stock residual includes cash and accruals; it is not available cash.",
        ],
        execution_authorized=False,
    )


def build_case(case_file, decision_time):
    """Read only explicitly named files; absent roles remain missing evidence."""
    try:
        return _build_case(case_file, aware(decision_time.isoformat()))
    except (
        KeyError,
        TypeError,
        AttributeError,
        DecimalException,
        OverflowError,
    ) as exc:
        raise ValueError("INVALID_STRATEGY_CASE") from exc


def _build_case(case_file, decision_time):
    path = safe_path(Path(case_file))
    case = read_json(path)
    if case["schema"] != "competition.strategy_case.v1":
        raise ValueError("INVALID_CASE_SCHEMA")
    declaration_root = _path(case["declaration_root"], path.parent)
    snapshot_root = _path(case["snapshot_root"], path.parent)
    declaration_hash = _declaration(declaration_root)
    snapshot, current, account = _snapshot(snapshot_root, decision_time)
    refs = case.get("sources", {})
    if not isinstance(refs, dict) or set(refs) - set(ROLES):
        raise ValueError("INVALID_SOURCE_ROLES")
    missing = [k for k in ROLES if k not in refs]
    sources = {"account": account}
    payloads = {}
    records = {
        "case": dict(path=str(path), sha256=digest(path)),
        "declaration": dict(
            path=str(declaration_root / "declaration.json"), sha256=declaration_hash
        ),
        "snapshot": dict(
            path=str(snapshot_root / "snapshot.json"), sha256=account["sha256"]
        ),
    }
    for k, ref in refs.items():
        source_path = _path(ref["path"], path.parent)
        if digest(source_path) != _hash(ref["sha256"]):
            raise ValueError("SOURCE_HASH_MISMATCH:" + k)
        effective, available = aware(ref["effective_at"]), aware(ref["available_at"])
        if not effective <= available <= decision_time:
            raise ValueError("NONCAUSAL_SOURCE:" + k)
        sources[k] = dict(
            sha256=ref["sha256"],
            effective_at=effective.isoformat(),
            available_at=available.isoformat(),
            parents=ref.get("parents", {}),
        )
        records[k] = dict(path=str(source_path), sha256=ref["sha256"])
        if k not in {"model", "pit"}:
            payloads[k] = read_json(source_path)
    for child, parents in [
        ("scores", ["pit", "universe", "model"]),
        ("target", ["scores"]),
    ]:
        if child in sources and all(k in sources for k in parents):
            if sources[child]["parents"] != {k: sources[k]["sha256"] for k in parents}:
                raise ValueError("PARENT_BINDING_MISMATCH:" + child)
    policy = payloads.get("policy", {})
    if policy:
        effective, confirmed = (
            aware(policy["effective_at"]),
            aware(policy["confirmed_at"]),
        )
        if (
            not effective
            <= confirmed
            <= aware(sources["policy"]["available_at"])
            <= decision_time
        ):
            raise ValueError("NONCAUSAL_POLICY")
        if (
            not isinstance(policy.get("confirmed_by"), str)
            or not policy["confirmed_by"].strip()
        ):
            raise ValueError("POLICY_CONFIRMATION_ATTRIBUTION_REQUIRED")
        if "target" in sources and confirmed > aware(sources["target"]["effective_at"]):
            raise ValueError("POLICY_CONFIRMED_AFTER_TARGET")
        if (
            policy["declaration_sha256"] != declaration_hash
            or policy["account_ref"] != snapshot["account_ref"]
        ):
            raise ValueError("POLICY_BINDING_MISMATCH")
    universe = payloads.get("universe", {}).get("symbols", [])
    if "universe" in payloads and (
        not isinstance(universe, list)
        or not universe
        or any(not isinstance(k, str) or not k for k in universe)
        or len(set(universe)) != len(universe)
    ):
        raise ValueError("INVALID_UNIVERSE")
    scores = _scores(payloads["scores"]["scores"]) if "scores" in payloads else {}
    target = _weights(payloads["target"]["weights"]) if "target" in payloads else {}
    if (
        (universe and set(scores) - set(universe))
        or (scores and set(target) - set(scores))
        or (universe and set(target) - set(universe))
    ):
        raise ValueError("SCORE_UNIVERSE_TARGET_MISMATCH")
    inputs = dict(
        account_ref=snapshot["account_ref"],
        declaration_sha256=declaration_hash,
        sources=sources,
        current_weights=current,
        target_weights=target,
        universe=universe,
        scheduled_review=case.get("scheduled_review", False),
    )
    decision = review_decision(policy, inputs, decision_time)
    if missing:
        decision["status"] = "blocked"
        decision["blockers"].extend("MISSING_FILE:" + k for k in missing)
    comparison = None
    if decision["status"] != "blocked":
        comparison = compare_weights(current, target, case["cost_bps"])
    return dict(
        schema="competition.strategy_case_review.v1",
        as_of=decision_time.isoformat(),
        account_ref=snapshot["account_ref"],
        report_date=snapshot["report_date"],
        base_currency=snapshot["base_currency"],
        current_weights=current,
        missing_roles=missing,
        file_records=records,
        daily_review=decision,
        comparison=comparison,
        model_semantics_verified=False,
        pit_truth_verified=False,
        source_times_independently_verified=False,
        declaration_independently_verified=False,
        official_eligibility="unverified",
        platform_account_binding="unverified",
        execution_authorized=False,
        account_age_basis="UTC start of report-date label, not exchange execution time",
        limitations=[
            "File identity and attributed causal references do not prove model training, PIT correctness or predictive skill.",
            "A prospective policy does not establish the basis of earlier orders.",
            "Review-required comparisons are diagnostic, never an allocation recommendation or execution handoff.",
        ],
    )
