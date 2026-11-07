"""Explicit private Flex reporting commands; no trading or scheduled activation."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from competition_tools.crypto_evidence import new_output, seal
from competition_tools.datasets.daily_storage import safe_path
from .flex_client import load_config, fetch_report, http_get, FlexError
from .flex_reports import discover_report, inspect_report
from .flex_ledger import summarize_ledger


def _write(out, name, value):
    data = (
        value
        if isinstance(value, bytes)
        else (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    )
    fd = os.open(out / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def _finish(out):
    seal(out)
    (out / "seal.json").chmod(0o600)


def collect(
    config_file,
    output,
    *,
    start=None,
    end=None,
    transport=http_get,
    sleep=time.sleep,
    discover=False,
    report_file=None,
):
    config = load_config(config_file)
    if not discover and not config.expected_account:
        raise FlexError("FLEX_ACCOUNT_BINDING_REQUIRED")
    inputs = [Path(config_file)]
    if report_file:
        report_file = safe_path(Path(report_file))
        inputs.append(report_file)
    out = new_output(output, inputs=inputs)
    out.chmod(0o700)
    receipt = dict(
        schema="competition.flex_receipt.v1",
        started_at=datetime.now(timezone.utc).isoformat(),
        account_ref=config.account_ref,
        requested_start=start,
        requested_end=end,
        mode="offline_inspection"
        if report_file
        else "discovery"
        if discover
        else "collection",
        status="requesting",
        execution_authorized=False,
        platform_account_binding="unverified",
    )
    try:
        if report_file:
            if report_file.stat().st_size > 16 * 1024 * 1024:
                raise FlexError("FLEX_RESPONSE_SIZE")
            raw = report_file.read_bytes()
        else:
            raw = fetch_report(
                config, start=start, end=end, transport=transport, sleep=sleep
            )
        if config.token.encode() in raw:
            raise FlexError("FLEX_SECRET_ECHO_REJECTED")
        if discover:
            observation = discover_report(raw)
            # Discovery does not retain the unbound raw report or position rows.
            _write(out, "discovery.json", observation)
            receipt.update(
                status="discovered",
                account_count=len(observation["accounts"]),
                raw_report_retained=False,
            )
        else:
            observation = inspect_report(
                raw,
                expected_account=config.expected_account,
                base_currency=config.base_currency,
                account_ref=config.account_ref,
            )
            ledger = summarize_ledger(raw, expected_account=config.expected_account)
            _write(out, "report.xml", raw)
            _write(out, "observation.json", observation)
            _write(out, "ledger.json", ledger)
            receipt.update(
                status="collected",
                report_sha256=hashlib.sha256(raw).hexdigest(),
                report_bytes=len(raw),
                official_daily_facts_complete=False,
            )
    except FlexError as exc:
        receipt.update(status="blocked", issue_code=str(exc))
    except (OSError, ValueError):
        receipt.update(status="blocked", issue_code="FLEX_LOCAL_OR_FORMAT_ERROR")
    receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write(out, "receipt.json", receipt)
    _finish(out)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["check-config", "discover", "collect", "inspect"]
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        if args.action == "check-config":
            config = load_config(args.config)
            print(
                json.dumps(
                    dict(
                        status="credentials_ready",
                        account_binding_complete=bool(
                            config.expected_account and config.base_currency
                        ),
                    )
                )
            )
            return 0
        if not args.output or (args.action == "inspect") != bool(args.report):
            raise FlexError("FLEX_INVALID_COMMAND_ARGUMENTS")
        receipt = collect(
            args.config,
            args.output,
            start=args.from_date,
            end=args.to_date,
            discover=args.action == "discover",
            report_file=args.report,
        )
        print(
            json.dumps(
                {
                    k: receipt[k]
                    for k in ["status", "account_ref", "execution_authorized"]
                }
                | (
                    {"issue_code": receipt["issue_code"]}
                    if "issue_code" in receipt
                    else {}
                )
            )
        )
        return 0 if receipt["status"] in ["collected", "discovered"] else 1
    except FlexError as exc:
        print(json.dumps(dict(status="blocked", issue_code=str(exc))))
        return 1
    except (OSError, ValueError):
        print(
            json.dumps(dict(status="blocked", issue_code="FLEX_LOCAL_OR_CONFIG_ERROR"))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
