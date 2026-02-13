# D4_synth_errors_seed42

Targeted error injections testing each invariant rule and mapping-stage drop path. E01–E04 should be dropped, E05 falls back to bookingDate, E06 is normalized by the pipeline.

## Properties

| Property | Value |
|---|---|
| Seed | 42 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked | 36 |
| Pending | 5 |
| Expected dropped | 4 |
| Expected outcome | PARTIAL_SUCCESS |

## What this dataset tests

Targeted error injections testing each invariant rule and mapping-stage drop path. E01–E04 should be dropped, E05 falls back to bookingDate, E06 is normalized by the pipeline.

## Variations / injected codes

  - `E01_INVALID_CURRENCY: currency='EURO' (4 chars) → INV-01 DROP`
  - `E02_MISSING_VALUE_DATE: no valueDate, no bookingDate → mapping DROP`
  - `E03_UNPARSEABLE_AMOUNT: amount='not_a_number' → mapping DROP (parse failure)`
  - `E04_EMPTY_CURRENCY: currency='' → INV-01 DROP`
  - `E05_VALUE_DATE_FALLBACK: no valueDate, has bookingDate → MAP-01 WARN, no drop`
  - `E06_LOWERCASE_CURRENCY: currency='eur' → pipeline uppercases, valid after normalize`

## Quality gate warnings

(none)
