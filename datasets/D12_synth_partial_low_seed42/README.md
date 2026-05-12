# D12_synth_partial_low_seed42

Low-rate error injection for gate sensitivity analysis. 1 E01-violations out of 200 records (0.50%) — used for parameteric sensitivity analysis of the operational quality gate.

## Properties

| Property | Value |
|---|---|
| Seed | 42 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked (total) | 200 |
| Pending (total) | 0 |
| Expected dropped | 1 |
| Expected outcome | PARTIAL_SUCCESS |

## What this dataset tests

Low-rate error injection for gate sensitivity analysis. 1 E01-violations out of 200 records (0.50%) — used for parameteric sensitivity analysis of the operational quality gate.

## Variations / injected codes

  - `E01_INVALID_CURRENCY #1: currency='EURO' → ERROR DROP`

## Quality gate warnings

- D12_synth_partial_low_seed42: transactions.json $.transactions.booked[199] currency 'EURO' invalid
