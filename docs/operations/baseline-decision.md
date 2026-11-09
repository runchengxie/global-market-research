# Common-ledger baseline decisions

[简体中文](baseline-decision.zh-CN.md) · [Research candidates](research-candidates.md)

Compare a small set of hypotheses on identical data, dates and accounting before expanding model capacity. The offline baseline study reuses the existing cash-funded USD adjusted-unit simulator. It supplies a private historical diagnostic, with every requested case retained and the declaration-bound Ranker explicitly unavailable. It exports no targets or orders.

## Protocol and scope

Seal an external `protocol.json` with schema `competition.baseline_decision_protocol.v1`. Bind the source manifest SHA256, source revision and exact adapter implementation SHA256. Record an aware `frozen_at`, symbol USMV/currency USD, ordered XNYS `start`/`end`, `sma_lookback` (integer 2–252), `stock_weight` (positive fraction at most one), ordered unique `one_way_cost_bps` (0–100, at most eight and including a positive fee), numerical tolerance, positive material-improvement threshold and a positive required-share numerator/denominator. `history_previously_examined` must be true; `parameter_optimization` and `execution_authorized` must be false. Source acquisition must precede the current retrospective freeze and all marks must be available in the retained response.

Use the sealed four-source manifest already supported by [ETF rehearsal](etf-rehearsal.md). The adapter verifies those bytes but only USMV contributes returns or sample size. It requires complete exact XNYS sessions and positive opening/closing values, with no filling. Existing historical adjustments and modeled clocks do not certify historical data availability or independent prices. No provider request or new model fit is performed.

```bash
python -m competition_tools.competition_review.baseline_decision \
  --manifest /external/sealed-inputs/manifest.json \
  --protocol /external/sealed-protocol \
  --output /external/new-baseline-study
```

Use the locked root daily-data/test environment. Output is a fresh external sealed directory with study.json and linked bilingual reports. Existing outputs are refused. Code changes require a new implementation binding and an explicitly recorded new version; preserve earlier results.

## Arms and common accounting

| Arm | Definition |
| --- | --- |
| `cash` | Zero-yield USD residual |
| `buy_hold` | Full stock exposure on initial entry, then hold units |
| `partial_hold` | Protocol stock weight on entry, then hold units and exposure drift |
| `fixed_monthly` | Reset to the protocol stock weight on monthly opening checkpoints |
| `sma_monthly` | At the same checkpoints, hold the protocol weight only when the prior completed close is strictly above its trailing SMA |
| `declared_ranker` | Unavailable with null metrics; no declaration-bound fitted model is supplied |

All arms share opening marks, entry/rebalance/terminal fees and cash-funded post-fee weight calculation. SMA includes the prior completed day and uses only closes before entry. Equality means cash; missing history blocks calculation. Monthly signals do not cause daily rebalances. Drawdown includes pre-entry wealth one. Keep signals, holdings, cash, trades and costs. Risk uses opening marks, with descriptive annualization.

Every annual episode resets at NAV1; partial years remain visible outside the full-year screen. Do not concatenate reset paths. USD adjusted-unit estimates omit account-base FX and actual financing. A current ETF selected after its history is known is not a historical broad-market membership sample. No net-alpha or actual-account result is established.

## Decision record

The SMA rule is paired with the same-cadence fixed arm, using return and drawdown differences at every cost. The frozen joint-improvement fraction screens this exact rule's research priority. Exposure remains different and no matched-risk claim follows. Every positive decision fee must meet its threshold. Missing requested cases make the screen unknown. Missing declared-model results always block a model-versus-baseline conclusion. Adoption authorization remains false.

Keep the earlier [volatility stopping decision](volatility-robustness.md) and frozen [prospective cycle](research-candidates.md) unchanged. Retain complete private metrics and an independent buy-and-hold trajectory check. Decide which hypotheses merit genuinely new observations only after reviewing evidence quality and source/account bindings. Do not change parameters after inspecting results.

Participation and financing remain separate reviews. The [official competition rules](https://fundconnecthk.com/quant-league/legal/competition-rules/) define eligibility using organizer position/turnover rates. Modeled turnover and target weights do not certify those rates. Preserve unresolved platform definitions and currency settlement facts rather than trading to manufacture activity.
