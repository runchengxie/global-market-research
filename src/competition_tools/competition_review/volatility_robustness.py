"""Aggregate sealed annual diagnostics under a frozen stopping rule, never adoption."""

import argparse
from datetime import datetime, date, timezone
import json
from pathlib import Path

from competition_tools.crypto_evidence import digest, read_json, verify_seal
from competition_tools.datasets.daily_storage import safe_path
from .evidence import aware
from .shadow import _save
from .strategy_case import _hash
from .volatility_math import number

CORE_KEYS = (
    "lookback_returns",
    "annualization",
    "target_volatility",
    "cap",
    "fixed_reference_weight",
    "one_way_cost_bps",
    "buffer_sensitivity",
    "cash_return",
    "leverage_allowed",
    "parameter_optimization",
    "execution_authorized",
    "match_tolerance",
)
ARMS = {
    "fixed_reference",
    "calibration_fixed",
    "volatility_control",
    "buffer_sensitivity",
    "hindsight_exposure_matched",
}


def required_passes(count, numerator, denominator):
    if (
        any(type(v) is not int for v in [count, numerator, denominator])
        or count < 0
        or not 1 <= numerator <= denominator <= 1000
    ):
        raise ValueError("INVALID_MAJORITY_RULE")
    return (count * numerator + denominator - 1) // denominator


def _canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _load(root, name, schema):
    root = safe_path(Path(root))
    verify_seal(root)
    value = read_json(root / name)
    if value["schema"] != schema:
        raise ValueError("UNKNOWN_ROBUSTNESS_INPUT_SCHEMA")
    return root, value


def _episodes(intent, original):
    import exchange_calendars as xc

    values = intent["episodes"]
    if not isinstance(values, list) or not 1 <= len(values) <= 100:
        raise ValueError("INVALID_EPISODE_COUNT")
    years = [date.fromisoformat(e["evaluation_start"]).year for e in values]
    schedule = xc.get_calendar(
        "XNYS", start=f"{min(years)}-01-01", end=f"{max(years)}-12-31"
    ).schedule
    by_year = {}
    for label in schedule.index:
        by_year.setdefault(label.year, []).append(label.date().isoformat())
    out = {}
    previous_end = intent["calibration_end"]
    for e in values:
        start, end = e["evaluation_start"], e["evaluation_end"]
        year = date.fromisoformat(start).year
        if (
            e["id"] != str(year)
            or e["id"] in out
            or date.fromisoformat(end).year != year
            or not previous_end < start < end
            or any(date.fromisoformat(d).isoformat() != d for d in [start, end])
        ):
            raise ValueError("INVALID_ORDERED_EPISODE_DATES")
        if start not in by_year[year] or end not in by_year[year]:
            raise ValueError("EPISODE_SESSION_REQUIRED")
        full = start == by_year[year][0] and end == by_year[year][-1]
        seen = any(
            start <= original[b] and end >= original[a]
            for a, b in [
                ("calibration_start", "calibration_end"),
                ("evaluation_start", "evaluation_end"),
            ]
        )
        flags = (full, seen, full and not seen)
        if any(
            type(e[k]) is not bool or e[k] != v
            for k, v in zip(
                ["full_calendar_year", "previously_examined", "include_in_decision"],
                flags,
            )
        ):
            raise ValueError("EPISODE_CLASSIFICATION_MISMATCH")
        out[e["id"]] = e
        previous_end = end
    return out


def _case_map(study, costs, tolerance):
    cases = {}
    for case in study["cases"]:
        key = (case["arm"], case["one_way_cost_bps"])
        if key in cases or key[0] not in ARMS or key[1] not in costs:
            raise ValueError("DUPLICATE_OR_UNEXPECTED_CASE")
        m = case["result"]["metrics"]
        number(m["total_return"], low=-1, positive=True)
        number(m["maximum_drawdown"], low=-1, high=0, positive=True)
        number(m["mean_exposure"], high=1)
        number(m["sum_trade_turnover"])
        if case["hindsight_nontradable"] is not (
            key[0] == "hindsight_exposure_matched"
        ):
            raise ValueError("HINDSIGHT_LABEL_REQUIRED")
        cases[key] = case
    for fee in costs:
        v, f = (
            cases.get(("volatility_control", fee)),
            cases.get(("hindsight_exposure_matched", fee)),
        )
        if v is not None and f is not None:
            delta = (
                f["result"]["metrics"]["mean_exposure"]
                - v["result"]["metrics"]["mean_exposure"]
            )
            residual = number(f["match_residual"], low=-1, high=1)
            if (
                abs(delta) > tolerance
                or abs(residual) > tolerance
                or abs(delta - residual) > tolerance
            ):
                raise ValueError("EXPOSURE_MATCH_RESIDUAL_MISMATCH")
    return cases


def run(
    intent_root,
    original_protocol_root,
    runs_root,
    output,
    *,
    corroboration_root=None,
    now=None,
):
    try:
        return _run(
            intent_root,
            original_protocol_root,
            runs_root,
            output,
            corroboration_root=corroboration_root,
            now=now,
        )
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError("MALFORMED_ROBUSTNESS_INPUT") from exc


def _run(
    intent_root,
    original_protocol_root,
    runs_root,
    output,
    *,
    corroboration_root=None,
    now=None,
):
    stamp = aware((now or datetime.now(timezone.utc)).isoformat())
    intent_root, intent = _load(
        intent_root, "intent.json", "competition.volatility_robustness_intent.v1"
    )
    original_root, original = _load(
        original_protocol_root,
        "protocol.json",
        "competition.volatility_study_protocol.v1",
    )
    runs_root, runs = _load(
        runs_root, "runs.json", "competition.volatility_robustness_runs.v1"
    )
    if (
        intent["original_protocol_sha256"] != digest(original_root / "protocol.json")
        or set(intent["core_parameters"]) != set(CORE_KEYS)
        or _canonical(intent["core_parameters"])
        != _canonical({k: original[k] for k in CORE_KEYS})
    ):
        raise ValueError("ORIGINAL_CORE_MISMATCH")
    frozen = aware(intent["frozen_at"])
    if (
        not aware(original["frozen_at"])
        <= frozen
        <= aware(runs["recorded_at"])
        <= stamp
        or intent["execution_authorized"] is not False
        or runs["intent_sha256"] != digest(intent_root / "intent.json")
    ):
        raise ValueError("INTENT_CHRONOLOGY_OR_BINDING_MISMATCH")
    if (
        not date.fromisoformat(intent["calibration_start"]).isoformat()
        == intent["calibration_start"]
        < intent["calibration_end"]
        or date.fromisoformat(intent["calibration_end"]).isoformat()
        != intent["calibration_end"]
    ):
        raise ValueError("INVALID_CALIBRATION_DATES")
    core = intent["core_parameters"]
    tolerance = number(core["match_tolerance"], high=1e-4, positive=True)
    numerical = number(intent["numerical_tolerance"], high=1e-4)
    material = number(intent["material_improvement"], high=1, positive=True)
    if material <= numerical:
        raise ValueError("MATERIALITY_MUST_EXCEED_NUMERICAL_TOLERANCE")
    costs = core["one_way_cost_bps"]
    decision_fees = intent["decision_fees"]
    if (
        not isinstance(decision_fees, list)
        or not decision_fees
        or decision_fees != sorted(set(decision_fees))
        or not set(decision_fees) <= set(costs)
    ):
        raise ValueError("INVALID_DECISION_FEES")
    for fee in decision_fees:
        number(fee, high=100, positive=True)
    episodes = _episodes(intent, original)
    inputs = [intent_root, original_root, runs_root]
    manifest_path = safe_path(Path(runs["source_manifest_file"]))
    verify_seal(manifest_path.parent)
    manifest = read_json(manifest_path)
    manifest_hash = _hash(runs["source_manifest_sha256"])
    if (
        digest(manifest_path) != manifest_hash
        or manifest["schema"] != "competition.etf_rehearsal_inputs.v1"
        or set(manifest["sources"]) != {"usmv", "japan", "usdsgd", "usdjpy"}
    ):
        raise ValueError("ROBUSTNESS_SOURCE_MISMATCH")
    inputs.append(manifest_path.parent)
    for ref in manifest["sources"].values():
        path = safe_path(Path(ref["path"]))
        verify_seal(path.parent)
        if digest(path) != _hash(ref["sha256"]):
            raise ValueError("ROBUSTNESS_SOURCE_HASH_MISMATCH")
        inputs.append(path.parent)
    used_source = manifest["sources"]["usmv"]
    receipt = read_json(Path(used_source["path"]).parent / "receipt.json")
    receipts = [
        r
        for r in receipt["records"]
        if r["symbol"] == "USMV"
        and r["status"] == "received"
        and r["sha256"] == used_source["sha256"]
    ]
    if (
        len(receipts) != 1
        or not frozen
        <= aware(receipts[0]["requested_at"])
        <= aware(receipts[0]["finished_at"])
        <= stamp
    ):
        raise ValueError("PREACQUISITION_INTENT_REQUIRED")
    received = aware(receipts[0]["finished_at"])
    entries = {}
    for entry in runs["entries"]:
        if entry["id"] not in episodes or entry["id"] in entries:
            raise ValueError("DUPLICATE_OR_UNPLANNED_EPISODE")
        entries[entry["id"]] = entry
    comparisons, reports = [], []
    missing = sorted(set(episodes) - set(entries))
    complete = not missing
    for key, e in episodes.items():
        cases = {}
        missing_cases = []
        if key in entries:
            entry = entries[key]
            root, s = _load(
                entry["root"], "study.json", "competition.volatility_study.v1"
            )
            inputs.append(root)
            if (
                digest(root / "study.json") != entry["study_sha256"]
                or s["source_manifest_sha256"] != manifest_hash
                or s["used_source_sha256"] != used_source["sha256"]
            ):
                raise ValueError("STUDY_HASH_OR_SOURCE_MISMATCH")
            p = s["protocol"]
            if (
                p["schema"] != "competition.volatility_study_protocol.v1"
                or p["symbol"] != "USMV"
                or p["currency"] != "USD"
            ):
                raise ValueError("STUDY_IDENTITY_MISMATCH")
            if (
                _canonical({k: p[k] for k in CORE_KEYS}) != _canonical(core)
                or any(p[k] != e[k] for k in ["evaluation_start", "evaluation_end"])
                or any(
                    p[k] != intent[k] for k in ["calibration_start", "calibration_end"]
                )
                or p["manifest_sha256"] != manifest_hash
                or p["intent_sha256"] != runs["intent_sha256"]
            ):
                raise ValueError("STUDY_CORE_OR_WINDOW_MISMATCH")
            if (
                not received
                <= aware(p["frozen_at"])
                <= aware(s["recorded_at"])
                <= aware(runs["recorded_at"])
                <= stamp
            ):
                raise ValueError("STUDY_CHRONOLOGY_MISMATCH")
            if s["currency"] != "USD" or any(
                s[k] is not False
                for k in [
                    "accepted_research",
                    "actual_account_performance",
                    "execution_authorized",
                ]
            ):
                raise ValueError("RETROSPECTIVE_DIAGNOSTIC_REQUIRED")
            cases = _case_map(s, costs, tolerance)
            missing_cases = sorted(
                f"{arm}:{fee}"
                for arm in ARMS
                for fee in costs
                if (arm, fee) not in cases
            )
            if missing_cases:
                complete = False
        else:
            missing_cases = ["missing_episode"]
        reports.append(
            dict(
                episode_id=key,
                include_in_decision=e["include_in_decision"],
                status="complete" if not missing_cases else "incomplete",
                missing_cases=missing_cases,
            )
        )
        for fee in costs:
            v, f = (
                cases.get(("volatility_control", fee)),
                cases.get(("hindsight_exposure_matched", fee)),
            )
            gap = dd = residual = passed = None
            if v is not None and f is not None:
                vm, fm = v["result"]["metrics"], f["result"]["metrics"]
                gap = vm["total_return"] - fm["total_return"]
                dd = vm["maximum_drawdown"] - fm["maximum_drawdown"]
                residual = vm["mean_exposure"] - fm["mean_exposure"]
                passed = (
                    gap >= -numerical and dd >= -numerical and max(gap, dd) >= material
                )
            comparisons.append(
                dict(
                    episode_id=key,
                    evaluation_start=e["evaluation_start"],
                    evaluation_end=e["evaluation_end"],
                    one_way_cost_bps=fee,
                    include_in_decision=e["include_in_decision"],
                    decision_fee=fee in decision_fees,
                    return_difference=gap,
                    drawdown_difference=dd,
                    mean_exposure_difference=residual,
                    passes_frozen_comparison=passed,
                    status="available" if passed is not None else "missing_case",
                )
            )
    count = sum(e["include_in_decision"] for e in episodes.values())
    required = required_passes(
        count, intent["required_share_numerator"], intent["required_share_denominator"]
    )
    summaries = []
    for fee in decision_fees:
        values = [
            r
            for r in comparisons
            if r["include_in_decision"] and r["one_way_cost_bps"] == fee
        ]
        passing = [
            r["episode_id"] for r in values if r["passes_frozen_comparison"] is True
        ]
        summaries.append(
            dict(
                one_way_cost_bps=fee,
                planned_episodes=count,
                passing_episodes=len(passing),
                passing_ids=passing,
                unknown_episodes=sum(
                    r["passes_frozen_comparison"] is None for r in values
                ),
                required_passes=required,
                threshold_met=len(passing) >= required if count else None,
            )
        )
    decision = (
        "unknown_incomplete_plan"
        if not complete
        else "unknown_no_new_full_episodes"
        if not count
        else "continue_candidate_under_frozen_rule"
        if all(s["threshold_met"] for s in summaries)
        else "retire_primary_candidate_under_frozen_rule"
    )
    corroboration = None
    independent = "not_supplied"
    if corroboration_root is not None:
        root, c = _load(
            corroboration_root,
            "corroboration.json",
            "competition.volatility_source_corroboration.v1",
        )
        if (
            c["manifest_sha256"] != manifest_hash
            or type(c["compatible_adjusted_ohlc"]) is not bool
            or type(c["independent_upstream_verified"]) is not bool
        ):
            raise ValueError("CORROBORATION_SOURCE_MISMATCH")
        inputs.append(root)
        corroboration = dict(
            root=str(root),
            sha256=digest(root / "corroboration.json"),
            scope=c["comparison_scope"],
            compatible_adjusted_ohlc=c["compatible_adjusted_ohlc"],
            independent_upstream_verified=c["independent_upstream_verified"],
        )
        independent = (
            "partial_attributed_corroboration"
            if not c["compatible_adjusted_ohlc"]
            else "attributed_compatible_series_claim_not_independent_authentication"
        )
    result = dict(
        schema="competition.volatility_robustness.v1",
        recorded_at=stamp.isoformat(),
        intent_sha256=digest(intent_root / "intent.json"),
        original_protocol_sha256=intent["original_protocol_sha256"],
        runs_manifest_sha256=digest(runs_root / "runs.json"),
        source_manifest_sha256=manifest_hash,
        stopping_rule=dict(
            required_share_numerator=intent["required_share_numerator"],
            required_share_denominator=intent["required_share_denominator"],
            numerical_tolerance=numerical,
            material_improvement=material,
            decision_fees=decision_fees,
            comparison="return_gap>=-numerical and drawdown_gap>=-numerical and max(gaps)>=material",
        ),
        input_roots=dict(
            intent=str(intent_root),
            original_protocol=str(original_root),
            runs=str(runs_root),
            source_manifest=str(manifest_path),
        ),
        all_planned_episodes_complete=complete,
        missing_episode_ids=missing,
        new_full_episodes=count,
        required_passes=required,
        episodes=reports,
        comparisons=comparisons,
        fee_summaries=summaries,
        research_decision=decision,
        decision_stage="under_supplied_sealed_retrospective_studies_not_independently_replayed_here",
        independent_source_status=independent,
        corroboration=corroboration,
        adoption_ready=False,
        accepted_research=False,
        execution_authorized=False,
        limitations=[
            "Current retrospective annual-reset experiments, not unseen OOS or a continuous full-span broker return.",
            "Hindsight fixed exposure control is nontradable; a majority stopping rule is a predeclared research resource decision, not a universal investor utility standard or strategy invalidity proof.",
            "All planned years/arms/fees are required; prior/partial periods are shown but excluded from the new-full-year denominator.",
            "Source hashes/seals bind supplied studies and inputs but do not independently authenticate authorship, upstream data, corporate actions or historical publication semantics.",
            "Independent-source scope is reported separately; even a positive research continuation decision never authorizes adoption or account changes.",
        ],
    )

    def fmt(v):
        return "—" if v is None else f"{v * 100:.4f}pp"

    table = "\n".join(
        f"|{r['episode_id']}|{r['one_way_cost_bps']}|{r['include_in_decision']}|{fmt(r['return_difference'])}|{fmt(r['drawdown_difference'])}|{r['passes_frozen_comparison']}|"
        for r in comparisons
    )
    return _save(
        output,
        "robustness.json",
        result,
        inputs,
        f"# Volatility-control robustness stopping report\n\nDecision under supplied historical inputs: {decision}. New full-year denominator {count}, required passes at each decision fee {required}. Independent-source status: {independent}; actual adoption remains false. All planned episodes/cost cases retained; missing results make the plan unknown. Positive drawdown differences mean less negative drawdown. Prior/partial years are displayed but not counted. Annual resets include entry/exit fees and do not form a continuous multi-year account. Hindsight matched controls remain nontradable. No strategy invalidity/alpha/statistical or account-action claim.\n\n|Episode|Fee bp|New decision year|Return gap|Drawdown gap|Frozen comparison pass|\n|---|---:|---|---:|---:|---|\n"
        + table,
        f"# 波动控制稳健性与停止报告\n\n所提供历史输入下的研究决定：{decision}。新增完整年度分母{count}，每个决策费率需至少{required}年通过。独立来源状态：{independent}；实际采用仍为false。保留全部计划年份/费用场景，缺失会令计划结论未知。回撤差为正表示回撤更小。已看过与不完整年度展示但不计入新年度分母。每年重置含入场/清仓费用，不能拼成连续多年账户业绩；事后匹配对照不可部署。此停止规则不证明策略普遍无效、存在超额能力或统计优势，不授权账户操作。\n\n|年度|费用bp|计入新年度|收益差|回撤差|冻结比较通过|\n|---|---:|---|---:|---:|---|\n"
        + table,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--original-protocol", required=True)
    parser.add_argument("--runs", required=True)
    parser.add_argument("--corroboration")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    r = run(
        args.intent,
        args.original_protocol,
        args.runs,
        args.output,
        corroboration_root=args.corroboration,
    )
    print(
        r["research_decision"]
        + "; retrospective research only; no adoption or execution."
    )


if __name__ == "__main__":
    main()
