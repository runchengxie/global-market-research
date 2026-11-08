"""Current-time model-free candidate diagnostics, separate from actual-strategy gates."""

import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from competition_tools.crypto_evidence import read_json, digest, verify_seal
from competition_tools.datasets.daily_storage import safe_path
from .etf_rehearsal import parse_chart, sma_signal
from .research_cycle import _schedule
from .shadow import _save
from .evidence import aware


def _proposal(root):
    root = safe_path(Path(root))
    verify_seal(root)
    p = read_json(root / "proposal.json")
    if (
        p["schema"] != "competition.concrete_research_cycle.v1"
        or p["execution_authorized"] is not False
        or p["accepted_research"] is not False
        or p["core_identity"]["currency"] != "USD"
    ):
        raise ValueError("INVALID_RESEARCH_PROPOSAL")
    first = aware(p["schedule"]["initial_signal_deadline"]).date().isoformat()
    schedule = _schedule(
        first, aware(p["material_review"]["cutoff"]), aware(p["created_at"])
    )
    if schedule != p["schedule"]:
        raise ValueError("FROZEN_SCHEDULE_MISMATCH")
    return root, p, first


def _price_diagnostic(path, proposal, session, close, deadline, now):
    import exchange_calendars as xc

    path = safe_path(Path(path))
    verify_seal(path.parent)
    receipt = read_json(path.parent / "receipt.json")
    symbol = proposal["core_identity"]["symbol"]
    sha = digest(path)
    rows = [
        r
        for r in receipt["records"]
        if r["symbol"] == symbol and r["status"] == "received" and r["sha256"] == sha
    ]
    if len(rows) != 1:
        raise ValueError("PRICE_RECEIPT_MISMATCH")
    r = rows[0]
    if (
        not close
        <= aware(r["requested_at"])
        <= aware(r["finished_at"])
        <= now
        <= deadline
    ):
        raise ValueError("PRICE_ACQUISITION_WINDOW_MISMATCH")
    start = date.fromisoformat(r["requested_start"]).isoformat()
    end = date.fromisoformat(r["requested_end_exclusive"]).isoformat()
    if (
        start != r["requested_start"]
        or end != r["requested_end_exclusive"]
        or not start <= session < end
    ):
        raise ValueError("PRICE_REQUEST_RANGE_MISMATCH")
    data, exclusions = parse_chart(read_json(path), symbol, "USD", start, end)
    if any(v["date"] > session for v in data):
        raise ValueError("FUTURE_PRICE_SESSION")
    day = date.fromisoformat(session)
    cal = xc.get_calendar("XNYS", start=day - timedelta(days=400), end=day).schedule
    labels = [t.date().isoformat() for t in cal.index][-200:]
    schedule = {t.date().isoformat(): row for t, row in cal.iterrows()}
    lookup = {v["date"]: v for v in data}
    if (
        session not in schedule
        or aware(schedule[session]["close"].isoformat()) != close
    ):
        raise ValueError("SESSION_CLOSE_MISMATCH")
    if any(
        d not in lookup
        or lookup[d]["event_at"] != aware(schedule[d]["open"].isoformat())
        for d in labels
    ):
        raise ValueError("DAILY_PRICE_CLOCK_OR_COVERAGE_MISMATCH")
    closes = {v["date"]: v["close"] for v in data}
    above = sma_signal(closes, labels)
    return dict(
        kind="reported_close_vs_sma200_diagnostic",
        above_sma200=above,
        completed_sessions=len(labels),
        session_close=str(closes[session]),
        sma200=str(sum(closes[d] for d in labels) / 200),
    ), dict(
        path=str(path),
        sha256=sha,
        receipt_sha256=digest(path.parent / "receipt.json"),
        requested_at=r["requested_at"],
        received_at=r["finished_at"],
        exclusions=exclusions,
    )


def record(proposal_root, output, session_date, price_file=None, *, now=None):
    stamp = aware((now or datetime.now(timezone.utc)).isoformat())
    root, p, first = _proposal(proposal_root)
    deadlines = {first: aware(p["schedule"]["initial_signal_deadline"])}
    deadlines.update(
        {
            r["session_date"]: aware(r["review_deadline"])
            for r in p["schedule"]["daily_checks"]
        }
    )
    if session_date not in deadlines:
        raise ValueError("UNKNOWN_FROZEN_CHECKPOINT")
    deadline = deadlines[session_date]
    close = deadline - timedelta(minutes=30)
    signal = evidence = None
    error = None
    inputs = [root]
    if stamp < close:
        status = "not_due"
    elif stamp > deadline:
        status = "missed_deadline"
    elif price_file is None:
        status = "blocked_missing_input"
    else:
        try:
            signal, evidence = _price_diagnostic(
                price_file, p, session_date, close, deadline, stamp
            )
            status = "recorded_diagnostic"
            inputs.append(Path(price_file).parent)
        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            OSError,
            ArithmeticError,
        ):
            status = "blocked_invalid_input"
            signal = evidence = None
            error = "PRICE_EVIDENCE_REJECTED"
    result = dict(
        schema="competition.candidate_observation.v1",
        recorded_at=stamp.isoformat(),
        session_date=session_date,
        status=status,
        window_open=close.isoformat(),
        deadline=deadline.isoformat(),
        proposal_sha256=digest(root / "proposal.json"),
        signal_diagnostic=signal,
        price_evidence=evidence,
        input_error_code=error,
        timestamp_authentication="local_clock_only",
        scope="model_free_research_diagnostic_not_actual_strategy_decision",
        source_semantics_independently_verified=False,
        actual_strategy_confirmed=False,
        accepted_research=False,
        execution_authorized=False,
        target_weights=None,
        orders=None,
    )
    return _save(
        output,
        "observation.json",
        result,
        inputs,
        f"# Candidate research observation\n\nStatus: {status}. Session: {session_date}. Recorded at {stamp.isoformat()}; window {close.isoformat()} through {deadline.isoformat()}. This is a model-free research diagnostic, with no actual policy/model approval, allocation or order. Not-due/missed/blocked records have null signal and do not mean hold or cash. No backdating or automatic date shift. Any price receipt is local attributed evidence; split/action/source semantics remain unverified. Keep every version and count a checkpoint only once. See observation.json for frozen bindings and diagnostics.",
        f"# 候选研究观察\n\n状态：{status}。交易日：{session_date}。记录时间 {stamp.isoformat()}；窗口为 {close.isoformat()} 至 {deadline.isoformat()}。这里只记录无需模型的研究诊断，没有确认实际策略/模型，也没有配置或订单。未到期、错过或阻断记录的信号为空，不代表持有或空仓。不回填、不自动移动日期。价格回执仍是本机归属证据，拆股/行动/来源语义未独立认证。保留全部版本，同一检查点只计一次。固定绑定和诊断见 observation.json。",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proposal", required=True)
    p.add_argument("--session-date", required=True)
    p.add_argument("--price-file")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    r = record(a.proposal, a.output, a.session_date, a.price_file)
    print(r["status"] + "; research diagnostic only; no execution authorization.")


if __name__ == "__main__":
    main()
