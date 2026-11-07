"""Synthetic as-of valuation and dimensional reconciliation checks."""

from decimal import Decimal
import pytest

ACCOUNT = "DU0000000"
RAW = b"""<FlexQueryResponse type="AF"><FlexStatements count="1"><FlexStatement accountId="DU0000000" fromDate="20261026" toDate="20261106"><AccountInformation accountId="DU0000000" currency="USD"/><OpenPositions><OpenPosition accountId="DU0000000" currency="EUR" assetCategory="STK" symbol="SYNTH" conid="1" reportDate="20261106" position="2" markPrice="50" positionValue="100" multiplier="1" fxRateToBase="2" levelOfDetail="SUMMARY"/><OpenPosition accountId="DU0000000" currency="EUR" assetCategory="STK" symbol="SYNTH" conid="1" reportDate="20261106" position="2" markPrice="50" positionValue="100" multiplier="1" fxRateToBase="2" levelOfDetail="LOT"/></OpenPositions><EquitySummaryInBase><EquitySummaryByReportDateInBase accountId="DU0000000" currency="USD" reportDate="20261106" total="999" stock="200" stockLong="200" stockShort="0" cash="800" interestAccruals="-1" dividendAccruals="0"/></EquitySummaryInBase><CashReport><CashReportCurrency accountId="DU0000000" currency="BASE_SUMMARY" levelOfDetail="BaseCurrency" fromDate="20261026" toDate="20261106" endingCash="800" endingSettledCash="800"/><CashReportCurrency accountId="DU0000000" currency="EUR" levelOfDetail="Currency" fromDate="20261026" toDate="20261106" endingCash="100" endingSettledCash="100"/><CashReportCurrency accountId="DU0000000" currency="USD" levelOfDetail="Currency" fromDate="20261026" toDate="20261106" endingCash="600" endingSettledCash="600"/></CashReport><ConversionRates><ConversionRate reportDate="20261106" fromCurrency="EUR" toCurrency="USD" rate="2"/></ConversionRates></FlexStatement></FlexStatements></FlexQueryResponse>"""


def snapshot(raw=RAW):
    from competition_tools.competition_review.flex_reconciliation import (
        reconcile_snapshot,
    )

    return reconcile_snapshot(
        raw, expected_account=ACCOUNT, base_currency="USD", account_ref="paper"
    )


def test_stock_cash_and_accrual_bridge_no_lot_or_base_summary_double_count():
    r = snapshot()
    assert r["status"] == "reconciled_stock_cash"
    assert r["report_date"] == "2026-11-06"
    assert r["stock"]["value_base"] == "200"
    assert r["cash"]["value_base"] == "800"
    assert r["nav_bridge"]["residual"] == "0"
    assert len(r["stock"]["positions"]) == 1
    assert Decimal(r["stock"]["positions"][0]["observed_weight"]) == Decimal(200) / 999
    assert r["execution_authorized"] is False
    assert r["official_eligibility"] == "unverified"


@pytest.mark.parametrize(
    "change", ["local_mark", "stock_nav", "stale_positions", "missing_identity"]
)
def test_stock_inconsistency_blocks_observed_weights(change):
    raw = RAW
    if change == "local_mark":
        raw = raw.replace(b'markPrice="50"', b'markPrice="51"')
    if change == "stock_nav":
        raw = raw.replace(b'stockLong="200"', b'stockLong="210"')
    if change == "stale_positions":
        raw = raw.replace(
            b'conid="1" reportDate="20261106"', b'conid="1" reportDate="20261105"'
        )
    if change == "missing_identity":
        raw = raw.replace(b' conid="1"', b"")
    r = snapshot(raw)
    assert r["stock"]["status"] == "blocked"
    assert all(p["observed_weight"] is None for p in r["stock"]["positions"])


def test_stale_fx_is_not_carried_forward_for_cash():
    raw = RAW.replace(
        b'<ConversionRate reportDate="20261106"',
        b'<ConversionRate reportDate="20261105"',
    )
    r = snapshot(raw)
    assert r["cash"]["status"] == "blocked"
    assert r["cash"]["value_base"] is None
    assert len(r["cash"]["balances"]) == 2


def test_negative_currency_cash_is_preserved():
    raw = RAW.replace(b'endingCash="100"', b'endingCash="-50"').replace(
        b'endingCash="600"', b'endingCash="900"'
    )
    r = snapshot(raw)
    assert r["cash"]["status"] == "reconciled"
    assert r["cash"]["value_base"] == "800"
    assert any(Decimal(x["amount"]) < 0 for x in r["cash"]["balances"])


def test_ambiguous_cash_and_offsetting_unsupported_assets_remain_visible():
    duplicate = b'<CashReportCurrency accountId="DU0000000" currency="EUR" levelOfDetail="Currency" fromDate="20261026" toDate="20261106" endingCash="900"/>'
    r = snapshot(RAW.replace(b"</CashReport>", duplicate + b"</CashReport>"))
    assert r["cash"]["status"] == "blocked"
    r = snapshot(RAW.replace(b'total="999"', b'total="999" bonds="10" options="-10"'))
    assert r["status"] == "needs_review"
    assert set(r["unsupported_nav_assets"]) == {"bonds", "options"}


def test_offline_cli_adds_sealed_reconciliation_artifact(tmp_path):
    import json
    from competition_tools.competition_review.flex_cli import collect
    from competition_tools.crypto_evidence import verify_seal

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            dict(
                token="123456789012345678901234",
                query_id="123456",
                expected_account=ACCOUNT,
                base_currency="USD",
                account_ref="paper",
            )
        )
    )
    config.chmod(0o600)
    report = tmp_path / "source.xml"
    report.write_bytes(RAW)
    out = tmp_path / "inspection"
    result = collect(config, out, report_file=report)
    assert result["status"] == "collected"
    assert result["reconciliation_status"] == "reconciled_stock_cash"
    assert (
        json.loads((out / "snapshot.json").read_text())["status"]
        == "reconciled_stock_cash"
    )
    assert verify_seal(out)
    assert all(f.stat().st_mode & 0o077 == 0 for f in out.iterdir())


@pytest.mark.parametrize("conid", ["0", "-", "unknown"])
def test_invalid_contract_id_cannot_get_observed_weight(conid):
    r = snapshot(RAW.replace(b'conid="1"', ('conid="' + conid + '"').encode()))
    assert r["stock"]["status"] == "blocked"


def test_one_contract_with_two_symbols_is_ambiguous_not_two_positions():
    start = RAW.index(b"<OpenPosition ")
    end = RAW.index(b"/>", start) + 2
    extra = RAW[start:end].replace(b'symbol="SYNTH"', b'symbol="SYNTH_ALIAS"')
    raw = (
        RAW.replace(b"</OpenPositions>", extra + b"</OpenPositions>")
        .replace(b'stock="200"', b'stock="400"')
        .replace(b'stockLong="200"', b'stockLong="400"')
        .replace(b'total="999"', b'total="1199"')
    )
    r = snapshot(raw)
    assert r["stock"]["status"] == "blocked"
    assert all(p["observed_weight"] is None for p in r["stock"]["positions"])


def test_out_of_range_decimal_input_blocks_instead_of_crashing():
    r = snapshot(RAW.replace(b'markPrice="50"', b'markPrice="1e1000000"'))
    assert r["stock"]["status"] == "blocked"
    assert all(p["observed_weight"] is None for p in r["stock"]["positions"])


def test_latest_incomplete_summary_cannot_fall_back_to_older_snapshot():
    extra = b'<OpenPosition accountId="DU0000000" currency="EUR" assetCategory="STK" conid="2" reportDate="20261107" position="1" markPrice="1" positionValue="1" multiplier="1" fxRateToBase="2" levelOfDetail="SUMMARY"/>'
    raw = RAW.replace(b'toDate="20261106"', b'toDate="20261107"').replace(
        b"</OpenPositions>", extra + b"</OpenPositions>"
    )
    r = snapshot(raw)
    assert r["status"] == "needs_review"
    assert r["report_date"] == "2026-11-07"
    assert all(p["observed_weight"] is None for p in r["stock"]["positions"])


def test_incomplete_current_summary_and_unsupported_positions_remain_visible():
    incomplete = b'<OpenPosition accountId="DU0000000" currency="EUR" assetCategory="STK" conid="2" reportDate="20261106" position="1" levelOfDetail="SUMMARY"/>'
    r = snapshot(RAW.replace(b"</OpenPositions>", incomplete + b"</OpenPositions>"))
    assert r["stock"]["status"] == "blocked"
    option = incomplete.replace(b'assetCategory="STK"', b'assetCategory="OPT"')
    r = snapshot(RAW.replace(b"</OpenPositions>", option + b"</OpenPositions>"))
    assert r["status"] == "needs_review"
    assert r["unsupported_position_rows"][0]["asset_class"] == "OPT"
    assert "UNSUPPORTED_POSITION_SCOPE" in r["issues"]
