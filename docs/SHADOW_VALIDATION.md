# Shadow Validation Protocol

Before a public release, compare the deterministic screener against known special-situation cases.

## Acceptance criteria

A release candidate must:

1. Never promote an unclosed asset transfer into current NAV.
2. Never use basic market cap as the only valuation when material dilution exists.
3. Distinguish non-binding LOI from definitive agreement and closing.
4. Flag a material ATM / equity-line capacity relative to current market cap.
5. Distinguish warrant exercise proceeds from free dilution.
6. Preserve event chronology: announcement -> definitive -> closing -> go-live/revenue.
7. Emit DATA_HOLD when the cap table cannot be reconstructed with adequate confidence.
8. Reject or downgrade names with impractical liquidity.
9. Keep source/as-of metadata for manual overrides.
10. Avoid ranking a name solely because of a same-day price spike.

## Historical regression cases

These are behavior tests, not fixed investment conclusions.

| Case | Required behavior |
|---|---|
| AMOD | Announced BTC transfer must not enter current NAV before closing/funded proof. |
| AGPU | Pre-funded warrants must be included in near-FD economics; basic MC alone is insufficient. |
| CLRO | Merger consideration, financing shares/warrants and advisor equity must prevent basic-MC illusion. |
| GIPR | Warrant-inducement financing must show both cash proceeds and reload-warrant overhang. |
| GPRO | Cash + residual NewCo equity merger consideration must be separated; cash component is not an unconditional floor if adjustments exist. |
| LIDR | Large ATM capacity relative to market cap must materially penalize the screen. |
| AIB | Closed powered-site acquisition may advance event proof, but unsigned tenant discussions must not be counted as contracted revenue. |
| VIP | Strategic financing / debt cleanup can score positively, but uncontracted MW pipeline is not revenue. |
| GWH | Rescue financing and warrant overhang should prevent a headline-driven promotion without definitive operating proof. |

## Release gate

Public staging is eligible only when:

- unit tests pass,
- live SEC scan completes,
- no A-tier candidate has DATA_HOLD,
- all nine regression cases behave as expected,
- manual review finds no severe dilution false negative.

The public repository should contain sanitized examples rather than the private live watchlist or private manual overrides.
