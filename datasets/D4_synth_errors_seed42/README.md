# D4_synth_errors_seed42

Targeted error injections (E01–E04) that each violate S-00B schema constraints and produce ERROR-level drops. With 4 drops out of 39 records (10.3%), the drop ratio exceeds the default.yaml threshold of 5%, so the adapter outcome is FAILED.

## Properties

| Property | Value |
|---|---|
| Seed | 42 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked | 34 |
| Pending | 5 |
| Expected dropped | 4 |
| Expected outcome | FAILED |

## What this dataset tests

Targeted error injections (E01–E04) that each violate S-00B schema constraints and produce ERROR-level drops. With 4 drops out of 39 records (10.3%), the drop ratio exceeds the default.yaml threshold of 5%, so the adapter outcome is FAILED.

## Variations / injected codes

  - `E01_INVALID_CURRENCY: currency='EURO' (4 chars) → ERROR DROP`
  - `E02_MISSING_VALUE_DATE: no valueDate → ERROR DROP`
  - `E03_UNPARSEABLE_AMOUNT: amount='not_a_number' → ERROR DROP`
  - `E04_EMPTY_CURRENCY: currency='' → ERROR DROP`

## Quality gate warnings

- D4_synth_errors_seed42: $.transactions.booked[30] currency 'EURO' invalid
- D4_synth_errors_seed42: $.transactions.booked[31] missing valueDate
- D4_synth_errors_seed42: $.transactions.booked[32] amount 'not_a_number' does not match pattern
- D4_synth_errors_seed42: $.transactions.booked[33] currency '' invalid
