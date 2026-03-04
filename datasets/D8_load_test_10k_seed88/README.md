# D8_load_test_10k_seed88

Load test with 10 000 transactions (8 000 booked + 2 000 pending). Tests pipeline behaviour at production-scale volumes: determinism, performance, memory handling, and sort stability. All transactions are valid — expected outcome is SUCCESS.

## Properties

| Property | Value |
|---|---|
| Seed | 88 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked (total) | 8000 |
| Pending (total) | 2000 |
| Expected dropped | 0 |
| Expected outcome | SUCCESS |

## What this dataset tests

Load test with 10 000 transactions (8 000 booked + 2 000 pending). Tests pipeline behaviour at production-scale volumes: determinism, performance, memory handling, and sort stability. All transactions are valid — expected outcome is SUCCESS.

## Variations / injected codes

  (none)

## Quality gate warnings

(none)
