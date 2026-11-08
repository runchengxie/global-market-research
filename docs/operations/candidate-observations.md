# Model-free candidate observations

[简体中文](candidate-observations.zh-CN.md) · [Frozen candidate cycle](research-candidates.md)

A temporary account position, a declared strategy and an experimental signal are different evidence. Capture the owner's explanation with its received-at date; do not turn a later recollection into contemporaneous proof or assume a declared Ranker exists. Keep actual intent, broker-observed facts, model uncertainty and proposed future policy separate in a short decision brief.

For rule interpretation, use [official2026-10-13section4.2](https://fundconnecthk.com/docs/quant-competition-rules-2026-10-13.pdf#page=8) and [competition review](competition-review.md). The cited participation test concerns cumulative flat days and full-period rates; failing those conditions affects defense/award candidacy, not an automatic consecutive-ten-day expulsion. A placeholder position is neither proof of an effective strategy nor an official eligibility certificate. This clarification alone is not an instruction to change positions or manufacture trades.

## Record a research checkpoint

The existing declared-model diary intentionally requires PIT/model/score lineage. Do not relax it or fabricate a Ranker to record an ETF hypothesis. The separate manual offline command below uses the frozen research proposal and a public-chart receipt only, without importing a model, generating weights or authorizing orders:

```bash
python -m competition_tools.competition_review.candidate_observation \
  --proposal /external/sealed-proposal --session-date 2026-11-09 \
  --price-file /external/sealed-source/core.json \
  --output /external/new-observation
```

`--price-file` is optional; there is no CLI backdating option or network acquisition. Use a new external output directory each time. The proposal seal/schema and exact reconstructed calendar must agree, and the session must be its initial day or a listed checkpoint. Current UTC determines status:

| Condition | Status | Signal |
| --- | --- | --- |
| Before scheduled close | `not_due` | null |
| After close+30-minute deadline | `missed_deadline` | null |
| In window without price evidence | `blocked_missing_input` | null |
| In window with rejected price evidence | `blocked_invalid_input` | null |
| In window with valid diagnostic inputs | `recorded_diagnostic` | Reported close versus200-observation mean only |

Null does not mean hold, sell or cash. No date is shifted; late input cannot recreate an ex-ante record. Keep every version and count each checkpoint once rather than selecting a favorable capture afterward. Local seals/clocks do not independently authenticate pre-registration.

For a recorded diagnostic, the external raw chart parent must be sealed with receipt.json. The unique received record must bind the core symbol/USD, actual bytes and request range. Acquisition must start after the scheduled close and finish by recording; recording must be within the frozen deadline. Exactly200 completed XNYS sessions through that day and correct daily-open chart event stamps are required. The result preserves source/receipt hashes, capture times, exclusions and the computed comparison. Missing/partial/future/conflicting/stale sources remain blocked. Tampered proposals or unknown checkpoint dates fail before output.

Reported-close/SMA evidence does not certify historical split basis, provider publication rights, actual policy, model acceptance, complete FX/accounting inputs or trading readiness. Existing [declared-model review](competition-review.md) and [real-ledger evidence gates](etf-rehearsal.md) are unchanged. The workflow installs no scheduler, sends no message and touches no account. Before a real checkpoint, collect the actually completed bar and review data semantics; a saved future calendar is not a completed observation.

## One-page decision brief

Record these concrete items privately: current operating state and attributed reason; dated marked holdings and trade facts; difference from the declaration; benchmark/rules of proposed research candidates; still-unapproved actual risk budget and reviewer; pause/block conditions for missing or inconsistent inputs; the next frozen timestamp and required source receipt. Preserve the original explanation and any later rule correction separately. Do not silently rewrite a declaration or historical decision. Do not automatically promote an experimental50%weight into an account policy.
