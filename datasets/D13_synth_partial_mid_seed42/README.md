# D13_synth_partial_mid_seed42

Mid-rate error injection for gate sensitivity analysis. 3 E01-violations out of 100 records (3.00%) — used for parameteric sensitivity analysis of the operational quality gate.

## Properties

| Property | Value |
|---|---|
| Seed | 42 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked (total) | 100 |
| Pending (total) | 0 |
| Expected dropped | 3 |
| Expected outcome | PARTIAL_SUCCESS |

## What this dataset tests

Mid-rate error injection for gate sensitivity analysis. 3 E01-violations out of 100 records (3.00%) — used for parameteric sensitivity analysis of the operational quality gate.

## Variations / injected codes

  - `E01_INVALID_CURRENCY #1: currency='EURO' → ERROR DROP`
  - `E01_INVALID_CURRENCY #2: currency='EURO' → ERROR DROP`
  - `E01_INVALID_CURRENCY #3: currency='EURO' → ERROR DROP`

## Quality gate warnings

- D13_synth_partial_mid_seed42: transactions.json $.transactions.booked[97] currency 'EURO' invalid
- D13_synth_partial_mid_seed42: transactions.json $.transactions.booked[98] currency 'EURO' invalid
- D13_synth_partial_mid_seed42: transactions.json $.transactions.booked[99] currency 'EURO' invalid
