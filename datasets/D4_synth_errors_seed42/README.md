# D4_synth_errors_seed42

| Property | Value |
|---|---|
| Seed | 42 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked | 36 |
| Pending | 5 |
| Expected dropped | 4 |

## Variations / injected codes

  - `E01_INVALID_CURRENCY: currency='EURO' (4 chars) → INV-01 DROP`
  - `E02_MISSING_VALUE_DATE: no valueDate, no bookingDate → mapping DROP`
  - `E03_UNPARSEABLE_AMOUNT: amount='not_a_number' → mapping DROP (parse failure)`
  - `E04_EMPTY_CURRENCY: currency='' → INV-01 DROP`
  - `E05_VALUE_DATE_FALLBACK: no valueDate, has bookingDate → MAP-01 WARN, no drop`
  - `E06_LOWERCASE_CURRENCY: currency='eur' → pipeline uppercases it, valid after normalize`

## Quality gate warnings

(none)
