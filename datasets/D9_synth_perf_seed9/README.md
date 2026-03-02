# D9_synth_perf_seed9

Standard-scale performance dataset with ~1 000 transactions (800 booked + 200 pending). Represents a realistic 6-month bank statement (~5.5 tx/day). Validates MF6 (≤ 500 ms) and provides a scaling data point between D3 (150 tx) and D8 (10 000 tx). All transactions are valid — expected outcome is SUCCESS.

## Properties

| Property | Value |
|---|---|
| Seed | 9 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked (total) | 800 |
| Pending (total) | 200 |
| Expected dropped | 0 |
| Expected outcome | SUCCESS |

## What this dataset tests

MF6 performance requirement validation: the standard test dataset (≤ 1 000 transactions) must be processed in ≤ 500 ms. Also used as the middle data point in the three-point scaling analysis (D1: 7 tx → D9: 1 000 tx → D8: 10 000 tx) to demonstrate O(n) pipeline complexity with fixed startup overhead.

## Variations / injected codes

  (none)

## Quality gate warnings

(none)
