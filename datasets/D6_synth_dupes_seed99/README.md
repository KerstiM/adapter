# D6_synth_dupes_seed99

Duplicate detection dataset with exact duplicates (DUP01), near-duplicates differing by amount (DUP02), transactionId (DUP03), or remittance (DUP04). Tests record_id hash uniqueness.

## Properties

| Property | Value |
|---|---|
| Seed | 99 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked | 20 |
| Pending | 3 |
| Expected dropped | 0 |
| Expected outcome | SUCCESS |

## What this dataset tests

Duplicate detection dataset with exact duplicates (DUP01), near-duplicates differing by amount (DUP02), transactionId (DUP03), or remittance (DUP04). Tests record_id hash uniqueness.

## Variations / injected codes

  - `DUP01_EXACT: exact copy of booked[0] (transactionId=TX00000013)`
  - `DUP02_NEAR_AMOUNT: same txId=TX00000002, amount differs by 0.01`
  - `DUP03_NEAR_TXID: same content, different transactionId=TX00000019`
  - `DUP04_NEAR_REMITTANCE: same txId=TX00000020, remittance differs`

## Quality gate warnings

(none)
