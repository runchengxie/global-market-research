# Multi-asset allocation and crypto sleeves

[简体中文](multiasset-crypto.zh-CN.md) · [Documentation](../README.md)

This is an offline extension of the static allocation diagnostic. It asks whether distinct asset exposures and a small crypto sleeve improve a cash-backed reference after modeled costs. Historical comparisons do not authorize competition positions or establish independent out-of-sample performance.

## Design and boundaries

Use a small role-based universe covering equity, nominal government bonds, inflation-linked bonds, gold and broad commodities. Retain cash explicitly. A US low-volatility equity proxy does not represent global equities. Similar products can duplicate risk. Inflation-linked bonds retain real-rate risk, and commodity fund returns include their product structure and futures roll effects.

Bridgewater's [All Weather explanation](https://www.bridgewater.com/research-and-insights/the-all-weather-story) motivates balancing exposure to growth and inflation surprises. Equal capital and inverse volatility are simple comparison rules, not a reproduction of Bridgewater's proprietary allocation or full covariance-based risk parity. Inverse-volatility weights ignore correlations. Freeze the estimation interval, weight limits and rounding before acquiring new data. Record fitted weights separately from subsequent returns.

Compare the existing stock/cash reference, an equal-capital diversified reference and a fixed inverse-volatility reference. Add separately identified crypto arms to the diversified reference by replacing cash. This raises invested exposure and does not match total portfolio risk. For the larger crypto sleeves, include a cash-replacement equity control at the same weight. The smaller crypto sleeve has no capital-matched equity control and remains exploratory. Keep asset identifiers, dates, weights and measured private results in the external protocol and report. Do not optimize on observed returns.

## Crypto lanes

The first combined ledger may use listed bitcoin and ether products on the same US exchange-session calendar as the other products. A listed product has fees, a listing date and market-hour gaps. Its actual price history cannot be extended backward with spot prices. The issuer describes [IBIT's bitcoin exposure](https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf) and [ETHA's ether exposure](https://www.ishares.com/us/products/337614/ishares-ethereum-trust-etf). Product inclusion is a research choice, not a claim that the account is eligible to buy it.

Retained BTCUSDT/ETHUSDT spot data remains a separate lane. USDT is not USD. Weekend returns, funding/custody costs, exchange failures and the mark/decision clock need an explicit contract before combining spot with exchange-session ETF marks. Do not forward-fill US ETF prices onto a 24/7 trading clock and imply executable synchronized trades. Do not infer diversifying behavior from crypto's name or adopt an inflation-hedge guarantee.

[IBKR's permission guide](https://www.interactivebrokers.com/campus/trading-lessons/adding-cryptocurrency-trading-permissions/) describes separate eligibility and permission requirements. Neither general broker availability nor existing crypto research establishes the current competition Paper account's access, the organizer's treatment or execution-schema support. See [competition rules](../competition/rules.md). No broker requests, orders or account settings are part of this diagnostic.

## Existing replay and reproduction

Use the independently installed equity-lab CLI. Root workflows do not import leaf research code.

```sh
python -m equity_lab.backtest.static_allocation \
  --input '<complete-common-session-panel.json>' \
  --protocol '<frozen-static-allocation-protocol.json>' \
  --output '<new-study.json>'
```

The input is a list of `{date, open, close}` rows, with a complete symbol-to-positive-price map for each mark. The caller verifies exact common exchange sessions, listing coverage, source hashes and consistent daily adjustment factors. The existing `equity.static_allocation_protocol.v1` requires USD, zero cash yield, `fees_bps` equal to `[0, 10, 25]`, and `policies` equal to `[hold, monthly, drift]`. Dates, `threshold` and named `targets` are explicit. Use JSON strings for policy names. Each target sums to at most one, with residual cash. Dynamic inverse-volatility targets and cash interest are not implemented by this CLI. Supply fixed weights estimated only from the frozen prior interval.

Run the long common-history non-crypto panel separately from the shorter listing-limited crypto panel. Each has its own full baseline and complete matrix. Compare arms only within the same panel and period. Retain every result and the daily ledger. Report initial-capital drawdown, annualized volatility, costs, actual exposure and calendar-year returns, with partial years labeled. The terminal cost affects the last reported equity; the last weights describe holdings before liquidation.

Adjusted price units are retrospective distribution proxies, not broker shares or dated dividend cash flows. Returns use zero-yield USD cash and exclude account FX, taxes, financing and lot constraints. Quoted percentage fees are sensitivity scenarios, not a validated broker fee schedule. Drawdown samples opens and closes, not intraday extrema. One vendor's history is not independent price or corporate-action acceptance.

Missing sessions or unavailable product history block the affected panel. Keep failed acquisition receipts and do not shorten the sample silently. Acquisition is public, bounded and credential-free. Save protocols, scripts, input hashes, receipts, validation and interpretations outside Git under the owning project's data root. Preserve existing future-observation commitments and shared latest pointers. A subsequent forward study requires a separate frozen protocol.

## Acceptance

Check the installed replay implementation against its source hash and retained wheel. Recompute cash funding and marks independently, including entry and terminal fees, and check that future data cannot affect fitted weights. Validate relevant leaf tests and repository checks. A successful diagnostic establishes reproducibility within its assumptions. Adoption remains undecided until independent inputs, cash yield, account currencies, permissions and an executable policy have been reviewed.
