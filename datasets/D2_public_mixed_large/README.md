# D2_public_mixed_large

Large mixed dataset with natural Berlin Group sign convention (positive amounts on OUT) causing INV-05 WARNs. Pending transactions omit bookingDate. No drops expected.

## Properties

| Property | Value |
|---|---|
| Seed | 2 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked | 50 |
| Pending | 16 |
| Expected dropped | 0 |
| Expected outcome | PARTIAL_SUCCESS |

## What this dataset tests

Large mixed dataset with natural Berlin Group sign convention (positive amounts on OUT) causing INV-05 WARNs. Pending transactions omit bookingDate. No drops expected.

## Variations / injected codes

  - `WARN_INV05: booked[28] sign mismatch (IN with negative amount)`
  - `WARN_INV05: booked[9] sign mismatch (IN with negative amount)`
  - `WARN_INV05: booked[12] sign mismatch (IN with negative amount)`
  - `WARN_INV05: booked[24] sign mismatch (IN with negative amount)`
  - `WARN_INV05: booked[30] sign mismatch (IN with negative amount)`

## Quality gate warnings

(none)
