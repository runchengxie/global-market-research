from datetime import datetime, timezone
import pytest
from competition_tools.evaluation.sequence_governance import build_protocol
from competition_tools.datasets.research_evidence import BLOCKERS


def evidence():
    return dict(
        schema="competition.daily_research_evidence_gap.v1",
        status="blocked",
        accepted_research=False,
        execution_authorized=False,
        manifest_sha256="a" * 64,
        checks=[dict(code="RETAINED_BYTES_VERIFIED", status="passed")]
        + [dict(code=k, status="blocked") for k in BLOCKERS],
    )


def test_future_protocol_stays_draft_and_binds_limits():
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    result = build_protocol(evidence(), "2026-11-09", "2027-02-05", now)
    assert result["status"] == "draft_pending_owner_review"
    assert (
        result["accepted_research"] is False and result["execution_authorized"] is False
    )
    assert len(result["required_evidence"]) == len(BLOCKERS)
    assert result["stopping_rules"]["max_fits"] == 100


@pytest.mark.parametrize(
    "start,end", [("2026-11-01", "2027-01-01"), ("2027-02-05", "2026-11-09")]
)
def test_past_or_inverted_window_is_rejected(start, end):
    with pytest.raises(ValueError, match="FUTURE"):
        build_protocol(
            evidence(), start, end, datetime(2026, 11, 7, tzinfo=timezone.utc)
        )


def test_caller_claims_do_not_promote_evidence():
    e = evidence()
    e["accepted_research"] = True
    with pytest.raises(ValueError, match="EVIDENCE"):
        build_protocol(
            e, "2026-11-09", "2027-02-05", datetime(2026, 11, 7, tzinfo=timezone.utc)
        )
