# Static allocation diagnostic

[简体中文](static-allocation.zh-CN.md) · [README](../README.md)

Compare diversification and rebalancing before adding predictors. This standalone module uses `portfolio.cash_rebalance`, not the legacy daily target-weight engine. It has no broker or root-package imports.

Run in the leaf's locked Python 3.12 environment:

```sh
python -m equity_lab.backtest.static_allocation --input panel.json --protocol protocol.json --output new-result.json
```

The panel is a JSON array in strictly increasing ISO date order. Every row has exactly `date`, `open`, `close`; each price object must contain the same nonempty symbol set. Prices are positive finite numbers. The `_cash` name is reserved. Example row:

```json
{"date":"2024-01-02","open":{"A":100,"B":80},"close":{"A":101,"B":79}}
```

The caller must verify the full exchange-session calendar and provenance before running. No filling or missing-session inference occurs inside the replay. For distribution-adjusted units, opening and closing marks must use the same daily adjustment factor. Do not add dividend cash again.

The protocol must name the actual first/last panel dates, the complete policy/fee matrix, and long-only target weights totaling at most one:

```json
{
  "schema":"equity.static_allocation_protocol.v1",
  "start":"2024-01-02","end":"2024-12-31",
  "currency":"USD","cash_yield":0,"threshold":0.05,
  "fees_bps":[0,10,25],"policies":["hold","monthly","drift"],
  "targets":{"stock_cash":{"A":0.5},"diversified":{"A":0.5,"B":0.25}}
}
```

Residual weights are cash. Entry is at the first open. Monthly trades occur at the first supplied session of each new month. Drift trades use the preceding close's weights (including cash) and execute at the next supplied open. The threshold is an absolute weight difference; `0.05` means five percentage points. Fees apply to traded notional and are paid from portfolio wealth. Fractional units drift between trades. The last close liquidates all units and charges exit costs.

The immutable output includes input/protocol SHA256, every case, daily marks, transactions, observed open exposure and continuous-path annual returns. Calendar-year subperiods are not independent resets; boundary years may be partial. Drawdown includes initial capital, post-trade opens, closes and terminal cost, but not intraday extrema. Daily-close volatility annualizes by 252. `traded_initial_capital` is traded notional divided by initial capital (one), not official competition turnover. Final mark equity includes terminal cost; its weights and cash describe holdings immediately before liquidation. `terminal_cash` is the final post-liquidation balance. Transaction quantities are post-trade quantities.

Same target stock weight does not ensure equal average stock exposure or portfolio risk. Zero-yield USD cash is not SGD account cash. Adjusted units do not model tradable share quantities, dated distributions, lots, taxes, FX, withholding or independently accepted corporate actions. Full source and timing acceptance remain separate. No case is promoted to a strategy or an order.
