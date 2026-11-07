"""Non-executable daily evidence review for an explicitly supplied policy."""

import hashlib
import json
from datetime import timedelta
from .evidence import aware
from .participation import decimal


def review_decision(policy, inputs, decision_time):
    decision_time = aware(decision_time.isoformat())
    blockers = []
    reasons = []
    required = [
        "account_ref",
        "top_k",
        "entry_buffer",
        "exit_buffer",
        "name_cap",
        "gross_cap",
        "turnover_cap",
        "drift_band",
        "max_age_hours",
    ]
    if policy.get("status") != "confirmed":
        blockers.append("POLICY_UNCONFIRMED")
    if any(policy.get(k) is None for k in required):
        blockers.append("POLICY_INCOMPLETE")
    if not policy.get("account_ref") or inputs.get("account_ref") != policy.get(
        "account_ref"
    ):
        blockers.append("ACCOUNT_BINDING_UNVERIFIED")
    try:
        if (
            any(
                type(policy[k]) is not int or policy[k] < 0
                for k in ["top_k", "entry_buffer", "exit_buffer"]
            )
            or policy["top_k"] < 1
        ):
            raise ValueError("INVALID_COUNTS")
        for key in [
            "name_cap",
            "gross_cap",
            "turnover_cap",
            "drift_band",
            "max_age_hours",
        ]:
            if decimal(policy[key]) <= 0:
                raise ValueError("INVALID_LIMIT")
        if not isinstance(policy["benchmark"], str) or not policy["benchmark"]:
            raise ValueError("MISSING_BENCHMARK")
        for key in ["declaration_sha256", "model_sha256"]:
            if len(policy[key]) != 64 or any(
                c not in "0123456789abcdef" for c in policy[key]
            ):
                raise ValueError("INVALID_POLICY_BINDING")
    except (KeyError, TypeError, ValueError):
        blockers.append("POLICY_INVALID")
    if inputs.get("declaration_sha256") != policy.get(
        "declaration_sha256"
    ) or not policy.get("declaration_sha256"):
        blockers.append("DECLARATION_BINDING_UNVERIFIED")
    sources = inputs.get("sources", {})
    times = {}
    for key in ["account", "pit", "universe", "model", "scores", "target"]:
        try:
            source = sources[key]
            stamp = aware(source["available_at"])
            if len(source["sha256"]) != 64 or any(
                c not in "0123456789abcdef" for c in source["sha256"]
            ):
                raise ValueError("INVALID_HASH")
            effective = aware(source["effective_at"])
            if effective > stamp or stamp > decision_time:
                raise ValueError("FUTURE_EFFECTIVE_TIME")
            age = decision_time - effective
            if age < timedelta(0) or age > timedelta(
                hours=float(decimal(policy["max_age_hours"]))
            ):
                raise ValueError("STALE_OR_FUTURE")
            times[key] = stamp
        except (KeyError, ValueError, TypeError):
            blockers.append("SOURCE_UNAVAILABLE_OR_INVALID:" + key)
    try:
        if policy["model_sha256"] != sources["model"]["sha256"]:
            raise ValueError("MODEL_BINDING_MISMATCH")
        for child, parents in [
            ("scores", ["pit", "universe", "model"]),
            ("target", ["scores"]),
        ]:
            if sources[child]["parents"] != {k: sources[k]["sha256"] for k in parents}:
                raise ValueError("PARENT_BINDING_MISMATCH")
    except (KeyError, TypeError, ValueError):
        blockers.append("SOURCE_LINEAGE_UNVERIFIED")
    if all(k in times for k in ["pit", "universe", "model", "scores", "target"]):
        if (
            max(times["pit"], times["universe"], times["model"]) > times["scores"]
            or times["scores"] > times["target"]
        ):
            blockers.append("NONCAUSAL_SOURCE_CHAIN")
    try:
        current = {k: decimal(v) for k, v in inputs["current_weights"].items()}
        target = {k: decimal(v) for k, v in inputs["target_weights"].items()}
        universe = set(inputs["universe"])
        if not current or not target or not universe:
            raise ValueError("MISSING_WEIGHTS_OR_UNIVERSE")
        cap = decimal(policy["name_cap"])
        gross = decimal(policy["gross_cap"])
        if (
            gross > 1
            or cap > gross
            or sum(target.values()) > gross
            or max(target.values()) > cap
        ):
            reasons.append("TARGET_RISK_LIMIT")
        if sum(current.values()) > gross or max(current.values()) > cap:
            reasons.append("CURRENT_RISK_LIMIT")
        if len(target) > policy["top_k"] or any(
            k not in universe for k in current.keys() | target.keys()
        ):
            reasons.append("UNIVERSE_OR_CARDINALITY_REVIEW")
        changes = [
            abs(target.get(k, 0) - current.get(k, 0))
            for k in current.keys() | target.keys()
        ]
        if max(changes) > decimal(policy["drift_band"]):
            reasons.append("DRIFT_REVIEW")
        if sum(changes) > decimal(policy["turnover_cap"]):
            reasons.append("TURNOVER_REVIEW")
        if type(inputs["scheduled_review"]) is not bool:
            raise ValueError("INVALID_REVIEW_FLAG")
        if inputs["scheduled_review"]:
            reasons.append("SCHEDULED_REVIEW")
    except (KeyError, ValueError, TypeError):
        blockers.append("WEIGHTS_OR_POLICY_INVALID")
    binding = hashlib.sha256(
        json.dumps(
            dict(policy=policy, inputs=inputs), sort_keys=True, allow_nan=False
        ).encode()
    ).hexdigest()
    return dict(
        schema="competition.daily_review.v1",
        decision_time=decision_time.isoformat(),
        status="blocked"
        if blockers
        else "review_required"
        if reasons
        else "maintain_candidate",
        blockers=blockers,
        reasons=reasons,
        input_sha256=binding,
        execution_authorized=False,
        scope="supplied_evidence_only",
    )
