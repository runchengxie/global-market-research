"""Validate attributed daily statement facts; never infer organizer definitions."""

from datetime import date
from pathlib import Path
import re
from competition_tools.crypto_evidence import digest, read_json
from competition_tools.datasets.daily_storage import safe_path
from .evidence import START, END, aware
from .participation import daily_rows, summarize_days, future_bounds, decimal


def _refs(value, sources):
    if (
        not isinstance(value, list)
        or not value
        or any(type(x) is not str for x in value)
    ):
        raise ValueError("SOURCE_REFERENCES_REQUIRED")
    if len(set(value)) != len(value) or not set(value) <= set(sources):
        raise ValueError("INVALID_SOURCE_REFERENCES")


def load_statement_bundle(path, as_of, *, declaration_sha256):
    """Load reviewed local facts and bind every referenced source before reporting."""
    try:
        return _load(path, as_of, declaration_sha256)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("MALFORMED_STATEMENT_BUNDLE") from exc


def _load(path, as_of, declaration_sha256):
    path = safe_path(Path(path))
    as_of = aware(as_of.isoformat())
    raw = read_json(path)
    if raw["schema"] != "competition.statement_bundle.v1":
        raise ValueError("UNKNOWN_STATEMENT_SCHEMA")
    if raw["declaration_sha256"] != declaration_sha256:
        raise ValueError("DECLARATION_MISMATCH")
    if raw["rate_unit"] != "fraction":
        raise ValueError("FRACTIONAL_RATES_REQUIRED")
    for key in ["account_ref", "reviewed_by"]:
        if type(raw[key]) is not str or not raw[key].strip():
            raise ValueError("REVIEW_AND_ACCOUNT_REQUIRED")
    if not re.fullmatch("[A-Z]{3}", raw["base_currency"]):
        raise ValueError("BASE_CURRENCY_REQUIRED")
    if not isinstance(raw["sources"], list) or not 1 <= len(raw["sources"]) <= 512:
        raise ValueError("INVALID_SOURCE_COUNT")
    sources = {}
    for source in raw["sources"]:
        source_id = source["id"]
        relative = source["path"]
        if not isinstance(source_id, str) or not source_id or source_id in sources:
            raise ValueError("INVALID_SOURCE_ID")
        if not isinstance(relative, str) or "\\" in relative or ":" in relative:
            raise ValueError("RELATIVE_SOURCE_PATH_REQUIRED")
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ValueError("RELATIVE_SOURCE_PATH_REQUIRED")
        p = safe_path(path.parent / rel)
        if not p.is_relative_to(path.parent) or not p.is_file() or p == path:
            raise ValueError("INVALID_SOURCE_PATH")
        if digest(p) != source["sha256"]:
            raise ValueError("SOURCE_HASH_MISMATCH")
        sources[source_id] = dict(path=str(p), sha256=source["sha256"])
    calendar = raw["calendar"]
    if (
        calendar["full_period"] is not True
        or aware(calendar["period_start"]) != START
        or aware(calendar["period_end"]) != END
    ):
        raise ValueError("FULL_PERIOD_CALENDAR_ASSERTION_REQUIRED")
    if (
        calendar["status"] not in ["unconfirmed", "organizer_confirmed"]
        or not isinstance(calendar["id"], str)
        or not calendar["id"]
    ):
        raise ValueError("INVALID_CALENDAR_METADATA")
    _refs(calendar["source_ids"], sources)
    for metric in ["position_rate", "turnover_rate", "flat_day"]:
        definition = raw["definitions"][metric]
        if (
            definition["status"] not in ["unconfirmed", "organizer_confirmed"]
            or not isinstance(definition["description"], str)
            or not definition["description"].strip()
        ):
            raise ValueError("RATIO_DEFINITION_REQUIRED")
        _refs(definition["source_ids"], sources)
    sessions = calendar["sessions"]
    if not isinstance(sessions, list) or not 1 <= len(sessions) <= 512:
        raise ValueError("INVALID_SESSION_COUNT")
    labels = []
    closes = {}
    last_close = START
    for session in sessions:
        label = session["session_date"]
        if date.fromisoformat(label).isoformat() != label:
            raise ValueError("CANONICAL_SESSION_DATE_REQUIRED")
        opened, closed = aware(session["opens_at"]), aware(session["closes_at"])
        if not START <= opened < closed <= END or opened < last_close:
            raise ValueError("INVALID_OR_OVERLAPPING_SESSION")
        labels.append(label)
        closes[label] = closed
        last_close = closed
    if labels != sorted(set(labels)):
        raise ValueError("DUPLICATE_OR_UNSORTED_SESSIONS")
    if not isinstance(raw["days"], list) or len(raw["days"]) > 512:
        raise ValueError("INVALID_DAY_COUNT")
    elapsed = [label for label in labels if closes[label] <= as_of]
    for row in raw["days"]:
        label = row["session_date"]
        if label not in elapsed:
            raise ValueError("OUTSIDE_ELAPSED_CALENDAR")
        for field in ["account_ref", "base_currency"]:
            if field in row and row[field] != raw[field]:
                raise ValueError("MIXED_ACCOUNT_OR_CURRENCY")
        if type(row["complete_day"]) is not bool:
            raise ValueError("COMPLETENESS_FLAG_REQUIRED")
        _refs(row["source_ids"], sources)
        covered = aware(row["covered_through"])
        available = aware(row["available_at"])
        if not START <= covered <= available <= as_of:
            raise ValueError("INVALID_EVIDENCE_TIMING")
        if row["complete_day"] and covered < closes[label]:
            raise ValueError("INCOMPLETE_SESSION_COVERAGE")
    rows = daily_rows(elapsed, raw["days"])
    summary = summarize_days(rows) if rows else None
    known = [
        decimal(r["position_rate"]) for r in rows if r["position_rate"] is not None
    ]
    planning = dict(status="unsupported_leveraged_planning")
    if all(v <= 1 for v in known):
        planning = future_bounds(
            sum(known), len(known), len(rows) - len(known), len(labels) - len(elapsed)
        )
    return dict(
        schema="competition.reviewed_statement.v1",
        bundle_path=str(path),
        bundle_sha256=digest(path),
        declaration_sha256=declaration_sha256,
        account_ref=raw["account_ref"],
        base_currency=raw["base_currency"],
        reviewed_by=raw["reviewed_by"],
        sources=sources,
        calendar=calendar,
        definitions=raw["definitions"],
        claim_stage="attributed_reviewed_inputs_only",
        source_authenticity="not_independently_verified",
        daily_coverage=rows,
        summary=summary,
        position_planning=planning,
        official_eligibility="unverified",
        execution_authorized=False,
    )
