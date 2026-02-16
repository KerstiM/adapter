# D7 — Standing Orders (seed 77)

Focused dataset for validating standing-order / INFORMATION transaction mapping
via the `nextExecutionDate` fallback introduced in Task 5.

## Contents

| File                   | Description                                           |
|------------------------|-------------------------------------------------------|
| accounts.json          | Single EUR current account                            |
| transactions.json      | 1 booked transaction, empty pending array             |
| standing_orders.json   | 3 INFORMATION standing-order items (see details below)|

## Standing-order items

| # | creditorName          | valueDate  | nextExecutionDate | Expected value_date |
|---|-----------------------|------------|-------------------|---------------------|
| 1 | Stadtwerke Berlin     | _(absent)_ | 2025-02-01        | 2025-02-01 (fallback to nextExecutionDate) |
| 2 | Vonovia SE            | 2025-02-01 | 2025-03-01        | 2025-02-01 (valueDate takes precedence)    |
| 3 | Allianz Versicherung  | _(absent)_ | 2025-04-01        | 2025-04-01 (fallback to nextExecutionDate) |

## Expected pipeline outcome

- **Outcome**: `SUCCESS` or `PARTIAL_SUCCESS`
- **accounts_total**: 1
- **transactions_total**: 4 (1 booked + 3 information)
- **transactions_emitted_sv**: 4
- **transactions_dropped**: 0

No error injections — all transactions should map successfully. Items 1 and 3
exercise the `coalesce(valueDate, nextExecutionDate)` fallback rule for
INFORMATION status; item 2 confirms that `valueDate` is preferred when present.

INFORMATION transactions are excluded from ML and LLM projections (C-02 / C-03
filter to BOOKED + PENDING only), so projections will contain only the single
booked transaction.
