"""Only synthetic accounts and credentials; no requests to IBKR."""

import json
import pytest

TOKEN = "123456789012345678901234"
QUERY = "123456"
ACCOUNT = "DU0000000"
REPORT = b"""<FlexQueryResponse type="AF"><FlexStatements count="1"><FlexStatement accountId="DU0000000" fromDate="20261026" toDate="20261106"><AccountInformation accountId="DU0000000" currency="USD"/><OpenPositions><OpenPosition accountId="DU0000000" currency="USD" assetCategory="STK" symbol="SYNTH" conid="100" reportDate="20261106" position="10" markPrice="20" positionValue="200" multiplier="1" fxRateToBase="1" levelOfDetail="SUMMARY"/></OpenPositions><Trades/><CashTransactions/><EquitySummaryInBase/></FlexStatement></FlexStatements></FlexQueryResponse>"""
SUCCESS = b"<FlexStatementResponse><Status>Success</Status><ReferenceCode>999</ReferenceCode><url>https://evil.invalid/steal</url></FlexStatementResponse>"
PENDING = b"<FlexStatementResponse><Status>Fail</Status><ErrorCode>1019</ErrorCode><ErrorMessage>wait</ErrorMessage></FlexStatementResponse>"


def test_config_placeholder_and_repr_do_not_expose_secret(tmp_path):
    from competition_tools.competition_review.flex_client import load_config, FlexError

    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            dict(
                token="",
                query_id="",
                expected_account="",
                account_ref="paper",
                base_currency="",
            )
        )
    )
    p.chmod(0o600)
    with pytest.raises(FlexError, match="CONFIG_INCOMPLETE"):
        load_config(p)
    raw = dict(
        token=TOKEN,
        query_id=QUERY,
        expected_account=ACCOUNT,
        account_ref="paper",
        base_currency="USD",
    )
    p.write_text(json.dumps(raw))
    p.chmod(0o600)
    config = load_config(p)
    assert (
        TOKEN not in repr(config)
        and QUERY not in repr(config)
        and ACCOUNT not in repr(config)
    )


def test_bounded_client_ignores_server_url_and_polls_same_reference():
    from competition_tools.competition_review.flex_client import (
        Credentials,
        fetch_report,
    )

    responses = iter([SUCCESS, PENDING, REPORT])
    calls = []
    waits = []

    def transport(endpoint, params):
        calls.append((endpoint, params))
        return next(responses)

    raw = fetch_report(
        Credentials(TOKEN, QUERY, ACCOUNT, "paper", "USD"),
        transport=transport,
        sleep=waits.append,
        max_polls=2,
    )
    assert raw == REPORT
    assert all(
        x[0].startswith(
            "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/"
        )
        for x in calls
    )
    assert calls[0][1]["q"] == QUERY and calls[1][1]["q"] == "999"
    assert waits == [10, 10]


def test_pending_is_bounded_and_auth_errors_are_sanitized():
    from competition_tools.competition_review.flex_client import (
        Credentials,
        fetch_report,
        FlexError,
    )

    c = Credentials(TOKEN, QUERY, ACCOUNT, "paper", "USD")
    calls = []

    def pending(endpoint, params):
        calls.append(1)
        return SUCCESS if len(calls) == 1 else PENDING

    with pytest.raises(FlexError, match="NOT_READY"):
        fetch_report(c, transport=pending, sleep=lambda n: None, max_polls=2)
    assert len(calls) == 3

    def auth(endpoint, params):
        return f"<FlexStatementResponse><Status>Fail</Status><ErrorCode>1012</ErrorCode><ErrorMessage>{TOKEN}</ErrorMessage></FlexStatementResponse>".encode()

    with pytest.raises(FlexError) as error:
        fetch_report(c, transport=auth, sleep=lambda n: None)
    assert TOKEN not in str(error.value)


def test_report_account_coverage_and_summary_lot_separation():
    from competition_tools.competition_review.flex_reports import inspect_report

    report = inspect_report(
        REPORT, expected_account=ACCOUNT, base_currency="USD", account_ref="paper"
    )
    assert report["account_match"] is True
    assert report["stock_positions"][0]["position_value"] == "200"
    assert report["official_daily_facts_complete"] is False
    assert report["execution_authorized"] is False
    assert report["sections"]["OpenPositions"]["row_count"] == 1
    raw = REPORT.replace(b'levelOfDetail="SUMMARY"', b'levelOfDetail="LOT"')
    assert (
        inspect_report(
            raw, expected_account=ACCOUNT, base_currency="USD", account_ref="paper"
        )["stock_positions"]
        == []
    )


@pytest.mark.parametrize(
    "change", ["account", "currency", "dtd", "bad_date", "duplicate"]
)
def test_bad_or_unbound_report_is_rejected(change):
    from competition_tools.competition_review.flex_reports import inspect_report
    from competition_tools.competition_review.flex_client import FlexError

    raw = REPORT
    if change == "account":
        raw = raw.replace(ACCOUNT.encode(), b"DU9999999")
    if change == "currency":
        raw = raw.replace(
            b'<AccountInformation accountId="DU0000000" currency="USD"',
            b'<AccountInformation accountId="DU0000000" currency="EUR"',
        )
    if change == "dtd":
        raw = b'<!DOCTYPE x [<!ENTITY y "secret">]>' + raw
    if change == "bad_date":
        raw = raw.replace(b'reportDate="20261106"', b'reportDate="20990101"')
    if change == "duplicate":
        a = raw.index(b"<OpenPosition ")
        b = raw.index(b"/></OpenPositions>") + 2
        raw = raw[:b] + raw[a:b] + raw[b:]
    with pytest.raises(FlexError):
        inspect_report(
            raw, expected_account=ACCOUNT, base_currency="USD", account_ref="paper"
        )


def test_collect_seals_private_files_without_credentials(tmp_path):
    from competition_tools.competition_review.flex_cli import collect
    from competition_tools.crypto_evidence import verify_seal

    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            dict(
                token=TOKEN,
                query_id=QUERY,
                expected_account=ACCOUNT,
                account_ref="paper",
                base_currency="USD",
            )
        )
    )
    p.chmod(0o600)
    responses = iter([SUCCESS, REPORT])
    calls = []

    def transport(endpoint, params):
        calls.append(endpoint)
        return next(responses)

    out = tmp_path / "report"
    result = collect(p, out, transport=transport, sleep=lambda n: None)
    assert result["status"] == "collected"
    assert verify_seal(out)
    for f in out.iterdir():
        assert f.stat().st_mode & 0o077 == 0
        assert TOKEN.encode() not in f.read_bytes()
    with pytest.raises(FileExistsError):
        collect(p, out, transport=transport, sleep=lambda n: None)
    assert len(calls) == 2


def test_transport_failure_receipt_contains_only_safe_code(tmp_path):
    from competition_tools.competition_review.flex_cli import collect
    from competition_tools.competition_review.flex_client import FlexError

    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            dict(
                token=TOKEN,
                query_id=QUERY,
                expected_account=ACCOUNT,
                account_ref="paper",
                base_currency="USD",
            )
        )
    )
    p.chmod(0o600)

    def failure(endpoint, params):
        raise FlexError("FLEX_TRANSPORT_UNAVAILABLE")

    out = tmp_path / "failure"
    result = collect(p, out, transport=failure, sleep=lambda n: None)
    assert result["status"] == "blocked"
    assert not (out / "report.xml").exists()
    assert TOKEN not in (out / "receipt.json").read_text()


def test_account_total_placeholder_is_not_another_account_or_position():
    from competition_tools.competition_review.flex_reports import (
        inspect_report,
        discover_report,
    )

    raw = REPORT.replace(
        b"<EquitySummaryInBase/>",
        b'<EquitySummaryInBase><EquitySummaryByReportDateInBase accountId="-" reportDate="20261106" total="1000"/></EquitySummaryInBase>',
    )
    assert discover_report(raw)["accounts"] == [ACCOUNT]
    result = inspect_report(
        raw, expected_account=ACCOUNT, base_currency="", account_ref="paper"
    )
    assert result["account_match"] is True
    assert result["base_currency"] == "USD"


def test_missing_account_information_keeps_base_currency_unknown():
    from competition_tools.competition_review.flex_reports import inspect_report

    raw = REPORT.replace(
        b'<AccountInformation accountId="DU0000000" currency="USD"/>', b""
    )
    result = inspect_report(
        raw, expected_account=ACCOUNT, base_currency="", account_ref="paper"
    )
    assert result["base_currency"] is None
    assert result["base_currency_match"] is None
    assert "BASE_CURRENCY_UNVERIFIED" in result["issues"]


def test_nav_summary_supplies_base_currency_and_execution_levels_are_not_orders():
    from competition_tools.competition_review.flex_reports import discover_report
    from competition_tools.competition_review.flex_ledger import summarize_ledger

    raw = REPORT.replace(
        b'<AccountInformation accountId="DU0000000" currency="USD"/>', b""
    )
    raw = raw.replace(
        b"<EquitySummaryInBase/>",
        b'<EquitySummaryInBase><EquitySummaryByReportDateInBase accountId="DU0000000" currency="USD" reportDate="20261106" total="1000" stockLong="200" stockShort="0" cash="800"/></EquitySummaryInBase>',
    )
    raw = raw.replace(
        b"<Trades/>",
        b'<Trades><Order accountId="DU0000000" levelOfDetail="ORDER"/><Trade accountId="DU0000000" levelOfDetail="EXECUTION" tradeID="1" ibOrderID="8" tradeDate="20261106" symbol="SYNTH" assetCategory="STK" currency="USD" buySell="BUY" quantity="10" transactionType="ExchTrade" ibCommission="-1" ibCommissionCurrency="USD"/></Trades>',
    )
    assert discover_report(raw)["base_currencies"][ACCOUNT] == ["USD"]
    result = summarize_ledger(raw, expected_account=ACCOUNT)
    assert result["executions"]["unique_records"] == 1
    assert result["executions"]["order_identifiers"] == 1
    assert result["stock_exposure_proxy"]["mean"] == "0.2"
    assert result["official_eligibility"] == "unverified"


def test_redirect_and_secret_echo_rejected_without_logging_values():
    from competition_tools.competition_review.flex_client import (
        _NoRedirect,
        FlexError,
        fetch_report,
        Credentials,
    )

    with pytest.raises(FlexError, match="REDIRECT_REJECTED"):
        _NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid")
    responses = iter(
        [
            SUCCESS,
            REPORT.replace(b"<Trades/>", f"<Trades><!--{TOKEN}--></Trades>".encode()),
        ]
    )
    with pytest.raises(FlexError, match="SECRET_ECHO") as error:
        fetch_report(
            Credentials(TOKEN, QUERY, ACCOUNT, "paper", "USD"),
            transport=lambda e, p: next(responses),
            sleep=lambda n: None,
        )
    assert TOKEN not in str(error.value)


def test_summary_placeholder_position_is_not_aggregated():
    from competition_tools.competition_review.flex_reports import inspect_report

    raw = REPORT.replace(
        b'<OpenPosition accountId="DU0000000"', b'<OpenPosition accountId="-"'
    )
    result = inspect_report(
        raw, expected_account=ACCOUNT, base_currency="USD", account_ref="paper"
    )
    assert result["stock_positions"] == []
    assert "POSITION_ROW_NOT_AGGREGATED" in result["issues"]


def test_conflicting_cash_or_execution_ids_fail_closed():
    from competition_tools.competition_review.flex_ledger import summarize_ledger
    from competition_tools.competition_review.flex_client import FlexError

    raw = REPORT.replace(
        b"<Trades/>",
        b'<Trades><Trade accountId="DU0000000" levelOfDetail="EXECUTION" tradeID="1" tradeDate="20261106"/><Trade accountId="DU0000000" levelOfDetail="EXECUTION" tradeID="1" tradeDate="20261106" quantity="999"/></Trades>',
    )
    with pytest.raises(FlexError, match="CONFLICTING_TRADE_ID"):
        summarize_ledger(raw, expected_account=ACCOUNT)


def test_missing_open_positions_does_not_mean_zero_holdings():
    from competition_tools.competition_review.flex_reports import inspect_report

    start = REPORT.index(b"<OpenPositions>")
    end = REPORT.index(b"</OpenPositions>") + len(b"</OpenPositions>")
    raw = REPORT[:start] + REPORT[end:]
    result = inspect_report(
        raw, expected_account=ACCOUNT, base_currency="USD", account_ref="paper"
    )
    assert "MISSING_SECTION:OpenPositions" in result["issues"]
    assert result["official_daily_facts_complete"] is False


def test_ledger_separates_contracts_and_rejects_outside_trade_dates():
    from competition_tools.competition_review.flex_ledger import summarize_ledger
    from competition_tools.competition_review.flex_client import FlexError

    trades = b'<Trades><Trade accountId="DU0000000" levelOfDetail="EXECUTION" tradeID="1" ibOrderID="1" tradeDate="20261106" conid="100" symbol="SYNTH" assetCategory="FUT" currency="USD" buySell="BUY" quantity="10" transactionType="ExchTrade"/><Trade accountId="DU0000000" levelOfDetail="EXECUTION" tradeID="2" ibOrderID="2" tradeDate="20261106" conid="200" symbol="SYNTH" assetCategory="FUT" currency="USD" buySell="SELL" quantity="-10" transactionType="ExchTrade"/></Trades>'
    raw = REPORT.replace(b"<Trades/>", trades)
    result = summarize_ledger(raw, expected_account=ACCOUNT)
    assert len(result["executions"]["groups"]) == 2
    assert {r["conid"] for r in result["executions"]["groups"]} == {"100", "200"}
    with pytest.raises(FlexError, match="DATE_OUTSIDE_REPORT"):
        summarize_ledger(
            raw.replace(b'tradeDate="20261106"', b'tradeDate="20200101"'),
            expected_account=ACCOUNT,
        )


def test_xml_encoded_secret_echo_is_not_saved():
    from competition_tools.competition_review.flex_client import (
        Credentials,
        fetch_report,
        FlexError,
    )

    encoded = "".join("&#" + str(ord(c)) + ";" for c in TOKEN).encode()
    raw = REPORT.replace(
        b'<FlexQueryResponse type="AF">',
        b'<FlexQueryResponse type="AF" queryName="' + encoded + b'">',
    )
    responses = iter([SUCCESS, raw])
    with pytest.raises(FlexError, match="SECRET_ECHO"):
        fetch_report(
            Credentials(TOKEN, QUERY, ACCOUNT, "paper", "USD"),
            transport=lambda e, p: next(responses),
            sleep=lambda n: None,
        )
