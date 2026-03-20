# D6_synth_dupes_seed99

Tests INV-09 duplicate record_id detection. Contains 3 exact duplicates (same hash inputs → same record_id → dropped with INV-09 WARN, keeping first deterministically) and 2 near-duplicates (different amount or remittance → different record_id → kept). Adapter should produce PARTIAL_SUCCESS with 3 INV-09 WARNs.

## Properties

| Property | Value |
|---|---|
| Seed | 99 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked (total) | 21 |
| Pending (total) | 3 |
| Expected dropped | 3 |
| Expected outcome | PARTIAL_SUCCESS |

## What this dataset tests

Tests INV-09 duplicate record_id detection. Contains 3 exact duplicates (same hash inputs → same record_id → dropped with INV-09 WARN, keeping first deterministically) and 2 near-duplicates (different amount or remittance → different record_id → kept). Adapter should produce PARTIAL_SUCCESS with 3 INV-09 WARNs.

## Variations / injected codes

  - `DUP-01_EXACT: exact copy of booked[0] (transactionId=TX00000013) → INV-09 DROP`
  - `DUP-02_EXACT: second copy of booked[0] (transactionId=TX00000013) → INV-09 DROP`
  - `DUP-03_EXACT: exact copy of booked[1] (transactionId=TX00000002) → INV-09 DROP`
  - `NEAR-01_DIFF_AMOUNT: same txId=TX00000007, amount differs → different record_id, kept`
  - `NEAR-02_DIFF_REMITTANCE: same txId=TX00000019, remittance differs → different record_id, both kept`

## Quality gate warnings

(none)
