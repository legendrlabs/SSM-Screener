---
name: special-situation-microcap
description: Deterministically screen U.S.-listed microcaps for source-backed special situations, including business pivots, mergers, asset-backed discounts, strategic investments, large contracts, balance-sheet cleanups, and dilution traps. Use SEC-first evidence, fully diluted economics, and PASS/WATCH/REJECT/DATA_HOLD gates.
---

# Special Situation Microcap Screener

## Purpose

Find U.S.-listed microcap special situations where market price may not yet reflect a verified structural change. This skill is a **screening and research-triage workflow**, not a trade recommendation engine.

## Non-negotiables

1. Use current SEC filings and current market data. Never rely on remembered price, shares outstanding, float, or financing terms.
2. Primary-source hierarchy: SEC filing/exchange notice → issuer IR exhibit → market-data provider → reputable secondary news.
3. Never use basic market cap alone when material pre-funded warrants, warrants, converts, preferreds, merger consideration, earnouts, or SBC exist.
4. If fully diluted economics cannot be reconstructed with reasonable confidence, output `DATA_HOLD`.
5. For asset-backed theses, calculate `mark-to-market asset value / fully diluted market cap`.
6. Non-binding LOIs and announced-but-unclosed asset transfers are not current assets.
7. A large contract headline is not revenue. Distinguish signed TCV, deposits, deployed assets, go-live, recognized revenue, and gross margin.
8. If the move already occurred, separate pre-move evidence, remaining current thesis, and momentum/squeeze/low-float effects.
9. Maximum five live candidates. Do not fill the list artificially.
10. If no candidate passes, state `NO CANDIDATE`.

## Deterministic status

- `PASS` — hard gates passed; deeper-research candidate.
- `WATCH` — thesis exists but event proof, liquidity, or dilution remains incomplete.
- `REJECT` — structural issue overwhelms the current thesis.
- `DATA_HOLD` — material data cannot be verified.

`PASS` means research priority, not a buy signal.

## Event proof hierarchy

- 0: rumor / promotional language / thematic mention
- 1: strategic review / preliminary / non-binding LOI
- 2: binding contract / definitive agreement / SPA
- 3: closed / funded / asset received
- 4: operating / go-live / recognized revenue

For announced asset transfers, do not include the asset in NAV before level 3.

## Required calculations

Always attempt to produce:

- `BASIC_SHARES`
- `NEAR_FD_SHARES`
- `STRICT_FD_SHARES`
- `BASIC_MC`
- `NEAR_FD_MC`
- `STRICT_FD_MC`
- `FD_RATIO`
- `ATM_RATIO`
- `NAV_COVERAGE` where relevant
- `ADV20`
- `EVENT_PROOF`
- `NEXT_CATALYST`

If cap-table confidence is low, do not guess; emit `DATA_HOLD`.

## SEC discovery modes

- `atom`: use on GitHub-hosted/public environments; discover filings via the official SEC Atom feed, then verify with submissions/companyfacts and the primary filing document.
- `daily-index`: use on local/self-hosted environments when EDGAR master-index access is available.
- `auto`: try daily-index first and fall back to Atom on HTTP 403.

The evidence standard is unchanged. If filing text or dilution terms cannot be verified, keep the candidate at `DATA_HOLD`.

## Runtime output order

When generated output files exist, read:

1. `output/quality.json`
2. `output/candidates.csv`
3. `output/dilution_check.csv`
4. `output/event_ledger.csv`
5. `output/latest.md`

If `SAFE_TO_ACT=false`, do not promote a ticker to PASS.

## Candidate review questions

For every surviving ticker answer:

1. What is the market currently treating this company as?
2. What is the company actually becoming?
3. What number may be missed?
4. Is that number large enough to matter?
5. Does dilution erase the apparent discount?
6. Would the thesis have existed three months earlier?
7. Does a reason remain at today's price?

## Final sections

- 오늘의 1순위
- 관찰만 할 종목
- 이미 늦은 종목
- 절대 건드리지 말 종목

These are research-priority buckets, not personalized investment instructions.
