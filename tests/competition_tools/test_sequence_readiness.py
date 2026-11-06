from datetime import datetime, timezone
import pytest
from competition_tools.evaluation.sequence_readiness import (
    build_preparation,
    validate_calendar,
)
from test_sequence_governance import evidence


def calendar():
    return dict(
        schema="equity_lab.sequence_forward_calendar.v1",
        calendar="XNYS",
        timezone="America/New_York",
        package="exchange_calendars",
        package_version="4.13.2",
        signal_start="2026-11-09",
        signal_end="2026-11-10",
        sessions=[
            dict(
                date="2026-11-09",
                open="2026-11-09T14:30:00+00:00",
                close="2026-11-09T21:00:00+00:00",
            ),
            dict(
                date="2026-11-10",
                open="2026-11-10T14:30:00+00:00",
                close="2026-11-10T21:00:00+00:00",
            ),
        ],
        final_entry=dict(date="2026-11-11", open="2026-11-11T14:30:00+00:00"),
        final_exit=dict(date="2026-11-12", open="2026-11-12T14:30:00+00:00"),
        observed_availability=False,
        registered_holdout=False,
    )


def plan():
    return dict(
        schema="equity_lab.sequence_target_plan.v1",
        folds=7,
        seeds=[11, 23, 37],
        fits=140,
        max_fits=180,
        seconds=21600,
        epochs=30,
        batch_size=128,
        patience=5,
        thresholds={
            "classification": [0.35, 0.425, 0.5, 0.575, 0.65],
            "regression": [0, 0.0005, 0.001, 0.002, 0.004],
        },
        hurdles={"classification": 0.5, "regression": 0.001},
        tasks=[
            dict(fold=f, objective=o, model=m, seed=s, fits=int(m != "prior"))
            for f in range(7)
            for o in ["classification", "regression"]
            for m in ["prior", "linear", "matched", "equal", "sparse"]
            for s in ([11] if m in ["prior", "linear"] else [11, 23, 37])
        ]
        + [
            dict(fold=f, objective="control", model=m, seed=0, fits=0)
            for f in range(7)
            for m in ["cash", "holding", "volatility10"]
        ],
    )


def test_preparation_never_promotes_candidates_to_accepted_evidence():
    result = build_preparation(
        evidence(), calendar(), plan(), datetime(2026, 11, 7, tzinfo=timezone.utc)
    )
    assert result["status"] == "frozen_preparation_blocked"
    assert result["registered_holdout"] is False
    assert (
        result["accepted_research"] is False and result["execution_authorized"] is False
    )
    assert len(result["required_evidence"]) == 6
    assert (
        result["candidate_selection"]
        == "all_frozen_candidates_no_retrospective_winner_selection"
    )
    assert result["final_exit"]["date"] == "2026-11-12"


@pytest.mark.parametrize("mutation", ["past", "duplicate", "exit", "attested", "naive"])
def test_bad_calendar_rejected(mutation):
    c = calendar()
    if mutation == "past":
        c["signal_start"] = "2026-11-01"
    if mutation == "duplicate":
        c["sessions"][1] = c["sessions"][0]
    if mutation == "exit":
        c["final_exit"] = c["final_entry"]
    if mutation == "attested":
        c["observed_availability"] = True
    if mutation == "naive":
        c["sessions"][0]["open"] = "2026-11-09T14:30:00"
    with pytest.raises(ValueError):
        validate_calendar(c, datetime(2026, 11, 7, tzinfo=timezone.utc))


def test_plan_fits_and_candidates_cannot_be_silently_changed():
    p = plan()
    p["fits"] = 139
    with pytest.raises(ValueError, match="PLAN"):
        build_preparation(
            evidence(), calendar(), p, datetime(2026, 11, 7, tzinfo=timezone.utc)
        )
