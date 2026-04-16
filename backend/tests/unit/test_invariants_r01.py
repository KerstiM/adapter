"""Direct unit tests for domain.rules.invariants_r01 — one test per invariant.

Each test constructs a minimal SV bundle that violates exactly one invariant
and asserts that the matching flag is emitted with the expected severity and
the transaction is kept or dropped as per R-01.
"""

from __future__ import annotations

from domain.rules.invariants_r01 import check_invariants, deduplicate_transactions
from tests.fakes import load_spec_rulesets

_R01 = load_spec_rulesets()["R-01"]


def _tx(**overrides) -> dict:
    """Build a valid baseline transaction that passes every invariant."""
    base: dict = {
        "record_id": "rec-001",
        "transaction_id": "TX001",
        "account_id": "acc-1",
        "status": "BOOKED",
        "value_date": "2025-06-01",
        "booking_date": "2025-06-01",
        "amount": {
            "currency": "EUR",
            "raw": "100.00",
            "signed": "100.00",
            "abs": "100.00",
        },
        "direction": "IN",
        "counterparty": {"role": "DEBTOR", "name": "Sender", "iban": "EE111"},
        "remittance": "payment",
        "flags": [],
        "source": {"input_file": "transactions.json", "input_path": "$.x[0]"},
    }
    base.update(overrides)
    return base


def _flag_ids(tx: dict) -> list[str]:
    return [f["id"] for f in tx["flags"]]


class TestINV01Currency:
    def test_valid_currency_keeps_tx(self) -> None:
        bundle = {"transactions": [_tx()]}
        valid, dropped = check_invariants(bundle, _R01)
        assert len(valid) == 1 and len(dropped) == 0
        assert "INV-01_CURRENCY_FORMAT" not in _flag_ids(valid[0])

    def test_lowercase_currency_drops_tx(self) -> None:
        tx = _tx()
        tx["amount"]["currency"] = "eur"
        valid, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(valid) == 0 and len(dropped) == 1
        flags = dropped[0]["flags"]
        assert any(
            f["id"] == "INV-01_CURRENCY_FORMAT" and f["severity"] == "ERROR"
            for f in flags
        )

    def test_four_letter_currency_drops_tx(self) -> None:
        tx = _tx()
        tx["amount"]["currency"] = "EURO"
        valid, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(dropped) == 1


class TestINV02ValueDateRequired:
    def test_missing_value_date_drops_tx(self) -> None:
        tx = _tx(value_date=None)
        valid, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(valid) == 0 and len(dropped) == 1
        assert any(
            f["id"] == "INV-02_VALUE_DATE_REQUIRED" and f["severity"] == "ERROR"
            for f in dropped[0]["flags"]
        )

    def test_empty_string_value_date_drops_tx(self) -> None:
        tx = _tx(value_date="")
        _, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(dropped) == 1


class TestINV03AmountParseable:
    def test_unparseable_raw_drops_tx(self) -> None:
        tx = _tx()
        tx["amount"]["raw"] = "abc"
        _, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(dropped) == 1
        assert any(
            f["id"] == "INV-03_AMOUNT_PARSEABLE" and f["severity"] == "ERROR"
            for f in dropped[0]["flags"]
        )

    def test_unparseable_signed_drops_tx(self) -> None:
        tx = _tx()
        tx["amount"]["signed"] = "NaN--"
        _, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(dropped) == 1

    def test_unparseable_abs_drops_tx(self) -> None:
        tx = _tx()
        tx["amount"]["abs"] = ""
        _, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(dropped) == 1


class TestINV04BookingDateOptional:
    def test_null_booking_date_keeps_tx(self) -> None:
        tx = _tx(booking_date=None)
        valid, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(valid) == 1 and len(dropped) == 0
        assert "INV-04_BOOKING_DATE_OPTIONAL" not in _flag_ids(valid[0])

    def test_invalid_booking_date_warns_but_keeps(self) -> None:
        tx = _tx(booking_date="not-a-date")
        valid, dropped = check_invariants({"transactions": [tx]}, _R01)
        assert len(valid) == 1 and len(dropped) == 0
        assert any(
            f["id"] == "INV-04_BOOKING_DATE_OPTIONAL" and f["severity"] == "WARN"
            for f in valid[0]["flags"]
        )


class TestINV09Dedupe:
    def test_single_record_kept(self) -> None:
        kept, drops = deduplicate_transactions([_tx()], _R01)
        assert len(kept) == 1 and len(drops) == 0

    def test_duplicate_by_account_and_record_id_flags_second(self) -> None:
        a = _tx(record_id="dup-1")
        a["source"]["input_path"] = "$.transactions.booked[0]"
        b = _tx(record_id="dup-1", transaction_id="TX002")
        b["source"]["input_path"] = "$.transactions.booked[1]"
        kept, drops = deduplicate_transactions([a, b], _R01)
        assert len(kept) == 1 and len(drops) == 1
        assert any(
            f["id"] == "INV-09_DUPLICATE_RECORD_ID" and f["severity"] == "WARN"
            for f in drops[0]["flags"]
        )

    def test_different_accounts_not_deduped(self) -> None:
        a = _tx(account_id="acc-1", record_id="rec-x")
        b = _tx(account_id="acc-2", record_id="rec-x")
        kept, drops = deduplicate_transactions([a, b], _R01)
        assert len(kept) == 2 and len(drops) == 0

    def test_dedup_winner_is_deterministic(self) -> None:
        a = _tx(record_id="dup-1", transaction_id="TX-B")
        a["source"]["input_path"] = "$.transactions.booked[1]"
        b = _tx(record_id="dup-1", transaction_id="TX-A")
        b["source"]["input_path"] = "$.transactions.booked[0]"
        kept1, _ = deduplicate_transactions([a, b], _R01)
        kept2, _ = deduplicate_transactions([b, a], _R01)
        assert kept1[0]["transaction_id"] == kept2[0]["transaction_id"]
