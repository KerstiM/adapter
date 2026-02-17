# D3_synth_valid_seed42

Multi-account synthetic baseline with separate report files per account. Two accounts (DE primary, EE secondary), each with its own transactions file. Sign-matched amounts, no error injections.

**Report files:** transactions_1.json, transactions_2.json

## Properties

| Property | Value |
|---|---|
| Seed | 42 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked (total) | 125 |
| Pending (total) | 25 |
| transactions_1.json | 100 booked + 20 pending (iban: DE43321819600133890838) |
| transactions_2.json | 25 booked + 5 pending (iban: EE402654235116155940) |
| Expected dropped | 0 |
| Expected outcome | SUCCESS |

## What this dataset tests

Multi-account synthetic baseline with separate report files per account. Two accounts (DE primary, EE secondary), each with its own transactions file. Sign-matched amounts, no error injections.

## Variations / injected codes

  (none)

## Quality gate warnings

(none)
