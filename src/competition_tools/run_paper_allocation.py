"""Offline allocation by default; explicit Paper submission and read-only recovery."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from apps.execution_runner.paper_allocation import PaperAllocationRunner
from apps.execution_runner.paper_spec import AllocationSpec
from competition_tools.project_storage import project_root
from packages.execution_policies.paper_allocation import (
    AllocationError,
    Quote,
    Snapshot,
    compute_allocation,
)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise AllocationError("duplicate_json_field")
        result[key] = value
    return result


def load_json(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs
    )


def load_snapshot(path):
    value = load_json(path)
    required = {
        "nav_sgd",
        "gross_sgd",
        "sgd_cash",
        "usd_cash",
        "sgd_settled",
        "usd_settled",
        "stock",
        "fx",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise AllocationError("invalid_snapshot_fields")
    quotes = {}
    for name in ("stock", "fx"):
        item = value[name]
        if not isinstance(item, dict) or set(item) != {"bid", "ask", "at", "live"}:
            raise AllocationError("invalid_quote_fields")
        quotes[name] = Quote(
            Decimal(item["bid"]),
            Decimal(item["ask"]),
            datetime.fromisoformat(item["at"]),
            item["live"],
        )
    return Snapshot(
        **{k: Decimal(value[k]) for k in required - {"stock", "fx"}}, **quotes
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument(
        "--mode", choices=("plan", "submit", "reconcile"), default="plan"
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="offline snapshot JSON; never acquires broker data",
    )
    parser.add_argument(
        "--data-root", type=Path, help="configured DATA_ROOT, required for broker modes"
    )
    parser.add_argument(
        "--execute-paper",
        action="store_true",
        help="explicitly enable this specified Paper attempt",
    )
    args = parser.parse_args(argv)
    broker = None
    try:
        spec = AllocationSpec.from_dict(load_json(args.spec))
        now = datetime.now(timezone.utc)
        spec.validate(now, check_window=False)
        if args.mode == "plan":
            if args.snapshot is None:
                raise AllocationError("offline_snapshot_required")
            plan = compute_allocation(spec.policy, load_snapshot(args.snapshot), now)
            print(
                json.dumps(
                    {
                        "status": "offline_plan",
                        "submitted": False,
                        "plan": asdict(plan),
                    },
                    default=str,
                )
            )
            return 0
        if args.data_root is None:
            raise AllocationError("explicit_data_root_required")
        if args.mode == "submit" and not args.execute_paper:
            raise AllocationError("explicit_paper_submission_flag_required")
        from adapters.ibkr.paper_allocation import IBKRPaperAllocationBroker

        broker = IBKRPaperAllocationBroker()
        root = project_root(args.data_root) / "paper-allocation"
        runner = PaperAllocationRunner(spec, root, broker)
        status = runner.run() if args.mode == "submit" else runner.reconcile()
        print(json.dumps({"status": status, "run_id": spec.run_id}))
        return {"reconciled": 0, "blocked": 2, "partial": 3, "unknown": 4}[status]
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": str(exc)
                    if isinstance(exc, AllocationError)
                    else "configuration_broker_or_io_error",
                }
            )
        )
        return 2
    finally:
        if broker is not None:
            broker.close()


if __name__ == "__main__":
    raise SystemExit(main())
