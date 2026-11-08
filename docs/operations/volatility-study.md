# Fixed exposure versus volatility-control research

[简体中文](volatility-study.zh-CN.md) · [ETF proxy diagnostics](etf-rehearsal.md)

This offline study asks whether time-varying sizing improves descriptive risk/return after controlling for exposure, cadence and fees. It consumes existing sealed historical chart inputs and an external sealed protocol. No network, broker, credentials, account target or scheduler is involved. The standalone accepted real-ledger replay remains unchanged.

[Moreira and Muir](https://www.nber.org/papers/w22208) motivate examining time-varying risk. Their inverse-variance factor study is not replicated by this capped inverse-volatility ETF experiment, and their results do not establish this experiment's effectiveness.

## Freeze before calculating outcomes

Create a new external directory with protocol.json and the existing evidence seal. Schema: `competition.volatility_study_protocol.v1`. Required fields: aware frozen_at; manifest_sha256; symbol/currency (the current adapter is USMV/USD only); calibration_start/calibration_end/evaluation_start/evaluation_end as ordered nonoverlapping canonical session dates; lookback_returns (2–252); annualization (integer1–366); target_volatility (positive fraction≤1); cap (1, unlevered); fixed_reference_weight (fraction0–1); sorted unique one_way_cost_bps (0–100, at most8); positive buffer_sensitivity≤1; cash_return0; leverage_allowed/parameter_optimization/execution_authorized false; positive match_tolerance≤0.0001. Parameters belong in the private protocol, not personal account policy.

The protocol and all input source/receipt hashes must match. Acquisition must precede protocol freezing, which must precede the current run. This is **current retrospective experiment freezing**, not historical preregistration. Vendor-adjusted history is not independent proof of historically available features. Do not relabel it unseen out-of-sample evidence.

```bash
python -m competition_tools.competition_review.volatility_study \
  --manifest /external/sealed-inputs/manifest.json \
  --protocol /external/sealed-protocol \
  --output /external/new-study
```

## Fair comparisons and accounting limits

All arms use the same USD adjusted opening proxies, zero-return USD residual and evaluation interval. The runner verifies the existing four-source manifest, but only USMV contributes to this experiment; Japanese/FX sources do not increase its sample size. Require exact XNYS history and warmup coverage with no filling. The previous completed adjusted closes provide trailing simple-return sample SD; annualize and apply target_vol/estimated_vol capped without leverage. Zero/missing volatility blocks instead of assigning full exposure. Model the decision at previous close+30minutes and changes at the next monthly opening mark. Between changes hold units, not daily fixed weights.

Arms are fixed_reference, calibration_fixed (earlier calibration-period average exposure, no return optimization), volatility_control, buffer_sensitivity, and hindsight_exposure_matched. The last is explicitly **nontradable**: its fixed weight is chosen using evaluation mean actual post-trade/pre-interval exposure. It diagnoses the lower-exposure explanation, not a deployable benchmark. Retain match residual/tolerance. Matching applies to the primary zero-buffer arm; the buffer arm separately measures a cadence sensitivity. Equal mean exposure does not imply equal realized risk or prove alpha.

Every arm starts with cash wealth1, pays entry/scheduled-adjustment fees on actual stock value changes, and liquidates at the final proxy mark with the same fee. Solve fees and target stock weights on post-fee wealth self-consistently; no borrowed cash. Drawdown includes pre-entry wealth1. Daily return volatility incorporates entry fee in the first interval and terminal fee in the last; it is opening-mark risk, not intraday risk. Turnover is the sum of modeled absolute stock changes divided by each pre-trade NAV, not an organizer daily rate. CAGR and annualized volatility describe the sample, not future returns.

Outputs retain all signal windows, clocks, paths, transactions, cost/buffer cases, calibration method and limitations in sealed bilingual reports/study.json. Adjusted opening units are non-executable proxies, with unverified historical publication/action semantics. Zero cash omits real interest, FX, taxes, spreads, market impact and financing. One ETF/time range and fee sensitivities are not independent validation trials. No threshold tuning, winner promotion, account allocation or competition eligibility conclusion follows automatically; the previously frozen prospective cycle is untouched.
