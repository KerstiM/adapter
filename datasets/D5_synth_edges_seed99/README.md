# D5_synth_edges_seed99

Schema-valid edge cases testing boundary conditions: zero amount, large amount, integer amount, sign conventions, same dates, long remittance, and missing counterparty (INV-10 WARN).

## Properties

| Property | Value |
|---|---|
| Seed | 99 |
| Date range | 2024-01-01 – 2024-12-31 |
| Booked (total) | 28 |
| Pending (total) | 5 |
| Expected dropped | 0 |
| Expected outcome | SUCCESS |

## What this dataset tests

Schema-valid edge cases testing boundary conditions: zero amount, large amount, integer amount, sign conventions, same dates, long remittance, and missing counterparty (INV-10 WARN).

## Variations / injected codes

  - `EDGE-01_ZERO_AMOUNT: amount='0.00' — valid but semantically odd`
  - `EDGE-02_LARGE_AMOUNT: amount='9999999.999' — max precision`
  - `EDGE-03_INTEGER_AMOUNT: amount='1' — valid per pattern ^-?\d+(\.\d{1,3})?$`
  - `EDGE-04_NEGATIVE_OUT: amount='-50.00' + creditorName → OUT, sign matches, no INV-05`
  - `EDGE-05_POSITIVE_IN: amount='100.50' + debtorName → IN, no INV-05`
  - `EDGE-06_SAME_DATES: bookingDate == valueDate == 2024-07-10`
  - `EDGE-07_LONG_REMITTANCE: 308 chars — valid, LLM projection truncates to 160`
  - `EDGE-08_NO_COUNTERPARTY: no creditor/debtor → direction by sign, INV-10 WARN`

## Quality gate warnings

(none)
