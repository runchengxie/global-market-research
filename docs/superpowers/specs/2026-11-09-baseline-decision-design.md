# Common-ledger baseline decision study

[简体中文](2026-11-09-baseline-decision-design.zh-CN.md)

Compare a small number of stock/cash policies under the same retained USMV adjusted-opening data, calendar, dates and accounting. Reuse the existing volatility-study cash-funded simulator. Add no broker, independent simulator, provider request, model training or execution handoff.

The external sealed protocol fixes the source manifest hash, retrospective freeze time, start/end sessions, SMA lookback, partial stock weight, costs and a research-screen threshold before calculating this study. Existing outcomes and source history have already been examined. All episodes remain retrospective; none becomes an untouched out-of-sample test through a new timestamp.

Each annual opening-mark episode starts at cash NAV1 and pays the same entry/rebalance/terminal costs. Arms are cash, full buy-and-hold, partial buy-and-hold, monthly fixed partial stock and monthly lagged-SMA partial stock. Keep the declared Ranker as unavailable with null metrics in every episode/cost, because no declaration-bound model is supplied. Cash earns zero USD. Keep every annual/partial episode and fee. Do not join reset episodes into a continuous account. Preserve all paths, decisions and trades.

SMA uses completed closes ending before the next opening mark, with strict greater-than selection. A scheduled monthly checkpoint uses only prior information. Valid equality means cash; missing history blocks calculation. Require complete exact XNYS history and no price filling. Fixed-hold arms do not reset daily. Partial-weight drift is retained. Annualized metrics are descriptive opening-mark estimates.

Compare SMA with the same-cadence fixed-weight reference. A frozen share threshold can screen whether this exact rule deserves more investigation, using joint return/drawdown gaps at every positive cost. It does not match exposure or establish alpha. Partial years stay visible outside the annual denominator. Model absence blocks any full model-versus-baseline conclusion. No outcome approves adoption or revises the previously frozen prospective cycle.

Keep actual calculations, raw sources and account/funding context private. Publish method and limitations only. Reconfirm public competition rules separately; modeled turnover is not the organizer rate, and a stock target does not establish award eligibility. Japan remains paused on its permission gate; crypto remains a separate research lane.
