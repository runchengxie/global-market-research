from datetime import date, datetime, timezone
from decimal import Decimal as D
import json

from competition_tools.run_paper_allocation import main
from apps.execution_runner.paper_spec import AllocationSpec
from packages.execution_policies.paper_allocation import AllocationPolicy


def test_cli_defaults_offline_and_requires_no_ibkr(tmp_path, capsys):
    now = datetime.now(timezone.utc)
    p = AllocationPolicy(
        D(".5"), D("20000"), 500, D("100"), date(2020, 1, 1), D(".01"), D(".00005")
    )
    spec = AllocationSpec(
        "demo", "DU123456", "TEST.US", 123, "ARCA", now, now.replace(microsecond=0), p
    )
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec.to_dict()))
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "nav_sgd": "10000",
                "gross_sgd": "0",
                "sgd_cash": "10000",
                "usd_cash": "0",
                "sgd_settled": "10000",
                "usd_settled": "0",
                "stock": {
                    "bid": "99.99",
                    "ask": "100",
                    "at": now.isoformat(),
                    "live": True,
                },
                "fx": {
                    "bid": "1.30",
                    "ask": "1.301",
                    "at": now.isoformat(),
                    "live": True,
                },
            }
        )
    )
    # Fix a valid window without needing an open market for offline planning.
    from datetime import timedelta

    spec = AllocationSpec(**{**vars(spec), "window_end": now + timedelta(minutes=10)})
    path.write_text(json.dumps(spec.to_dict()))
    assert main(["--spec", str(path), "--snapshot", str(snapshot)]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "offline_plan" and value["submitted"] is False
    assert value["plan"]["shares"] == 38


def test_duplicate_json_fields_fail_closed(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text('{"schema":"a","schema":"b"}')
    assert main(["--spec", str(path)]) == 2
    assert "blocked" in capsys.readouterr().out
