#!/usr/bin/env python3
"""
Generate deterministic PSD2/Berlin Group AIS test datasets D1–D6.

Each dataset produces:
  datasets/<name>/accounts.json
  datasets/<name>/transactions.json   (single-account datasets)
    — or —
  datasets/<name>/transactions_N.json (multi-account datasets, e.g. D3)
  datasets/<name>/README.md

Usage:
  python scripts/generate_datasets.py --out datasets/ --dataset all
  python scripts/generate_datasets.py --out datasets/ --dataset D3 --seed 42 --n 120 --start-date 2024-01-01 --end-date 2024-12-31

Requirements derived from Notes.md + S-00A / S-00B schemas:
  accounts.json  – S-00A: {"accounts": [{resourceId, iban, currency, ...}]}
  transactions.json – S-00B ReportResponse:
      {"account": {"iban": ...}, "transactions": {"booked": [...], "pending": [...]}}
  Tx required fields: transactionAmount {currency, amount}, valueDate
  Amount pattern: ^-?\\d+(\\.\\d{1,3})?$
  Currency pattern: ^[A-Z]{3}$
  IBAN pattern: ^[A-Z]{2}[0-9A-Z]{13,32}$
  IsoDate: YYYY-MM-DD

OPEN QUESTIONS:
  - Notes.md does not specify max IBAN length beyond schema regex (13–32 chars
    after country code). We use realistic 18–22 digit IBANs.
  - Notes.md does not define bankTransactionCode enum. We use common PMNT-*
    codes from ISO 20022.
"""

import argparse
import json
import random
import re
import string
import uuid
from datetime import date, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COUNTRY_IBANS = {
    "DE": {"len": 20, "currency": "EUR"},
    "NL": {"len": 16, "currency": "EUR"},
    "FR": {"len": 25, "currency": "EUR"},
    "EE": {"len": 18, "currency": "EUR"},
    "GB": {"len": 20, "currency": "GBP"},
    "SE": {"len": 22, "currency": "SEK"},
    "PL": {"len": 26, "currency": "PLN"},
}

FIRST_NAMES = [
    "Anna", "Jan", "Marie", "Peeter", "Katrin", "Mart", "Liisa", "Andres",
    "Laura", "Tomas", "Elena", "Carlos", "Sophie", "Luca", "Emma", "Henrik",
    "Olivia", "Markus", "Julia", "Stefan", "Ingrid", "Viktor", "Clara", "Felix",
]

LAST_NAMES = [
    "Tamm", "Kask", "Mets", "Lepp", "Saar", "Mueller", "Jansen", "Dubois",
    "Smith", "Rossi", "Nilsson", "Kowalski", "Berg", "Oja", "Kuusk", "Paju",
]

REMITTANCE_TEMPLATES = [
    "Invoice {ref}",
    "Salary {month}",
    "Rent payment {month}",
    "Subscription renewal",
    "Transfer to savings",
    "Grocery store purchase",
    "Utility bill {month}",
    "Insurance premium Q{q}",
    "Freelance payment {ref}",
    "Refund order {ref}",
    "Donation to charity",
    "Loan repayment {month}",
    "Service fee",
    "Tax payment {ref}",
    "Online purchase {ref}",
]

BTC_CODES = [
    "PMNT-IRCT-ESCT",
    "PMNT-ICDT-STDO",
    "PMNT-RDDT-ESDD",
    "PMNT-IRCT-XBCT",
    "PMNT-MCOP-OTHR",
]

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

class DatasetGenerator:
    """Seeded, deterministic generator for Berlin Group AIS test data."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self._tx_counter = 0

    def _random_iban(self, country: str | None = None) -> str:
        if country is None:
            country = self.rng.choice(list(COUNTRY_IBANS.keys()))
        spec = COUNTRY_IBANS[country]
        digits = "".join(str(self.rng.randint(0, 9)) for _ in range(spec["len"]))
        return f"{country}{digits}"

    def _random_uuid(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def _random_name(self) -> str:
        return f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"

    def _random_amount(self, lo: float = 1.0, hi: float = 9999.99) -> str:
        val = round(self.rng.uniform(lo, hi), 2)
        return f"{val:.2f}"

    def _random_date(self, start: date, end: date) -> date:
        delta = (end - start).days
        if delta <= 0:
            return start
        return start + timedelta(days=self.rng.randint(0, delta))

    def _next_tx_id(self) -> str:
        self._tx_counter += 1
        return f"TX{self._tx_counter:08d}"

    def _random_remittance(self, d: date) -> str:
        tpl = self.rng.choice(REMITTANCE_TEMPLATES)
        ref = "".join(self.rng.choices(string.ascii_uppercase + string.digits, k=8))
        month = MONTHS[d.month - 1]
        q = (d.month - 1) // 3 + 1
        return tpl.format(ref=ref, month=month, q=q)

    def generate_account(
        self,
        country: str = "DE",
        currency: str = "EUR",
        name: str = "Main Account",
        resource_id: str | None = None,
        iban: str | None = None,
    ) -> dict:
        return {
            "resourceId": resource_id or self._random_uuid(),
            "iban": iban or self._random_iban(country),
            "currency": currency,
            "product": "Current Account",
            "cashAccountType": "CACC",
            "name": name,
        }

    def generate_transaction(
        self,
        account_iban: str,
        start_date: date,
        end_date: date,
        *,
        direction: str | None = None,
        include_booking_date: bool = True,
        amount_str: str | None = None,
        currency: str = "EUR",
        value_date_str: str | None = None,
        booking_date_str: str | None = None,
        omit_value_date: bool = False,
        omit_amount: bool = False,
        bad_currency: str | None = None,
        bad_amount: str | None = None,
        force_sign_mismatch: bool = False,
        match_sign_to_direction: bool = False,
        counterparty_name: str | None = None,
        counterparty_iban: str | None = None,
        omit_counterparty: bool = False,
        transaction_id: str | None = None,
        remittance: str | None = None,
    ) -> dict:
        """Generate a single Berlin AIS transaction.

        match_sign_to_direction: if True, OUT amounts get "-" prefix and IN
            amounts stay positive, so that INV-05 does NOT fire.
        force_sign_mismatch: if True, forces sign that WILL trigger INV-05.
        """
        vd = date.fromisoformat(value_date_str) if value_date_str else self._random_date(start_date, end_date)
        bd = vd - timedelta(days=self.rng.randint(0, 2)) if include_booking_date else None
        if booking_date_str:
            bd = date.fromisoformat(booking_date_str)

        if direction is None:
            direction = self.rng.choice(["IN", "OUT"])

        # Amount
        raw_amount = amount_str or self._random_amount()
        if bad_amount is not None:
            raw_amount = bad_amount
        if omit_amount:
            raw_amount = None

        # Sign convention
        if raw_amount is not None:
            if match_sign_to_direction:
                # Ensure sign matches direction (no INV-05)
                abs_val = raw_amount.lstrip("-")
                if direction == "OUT":
                    raw_amount = "-" + abs_val
                else:
                    raw_amount = abs_val
            elif force_sign_mismatch:
                # Force sign that will trigger INV-05
                if direction == "IN" and not raw_amount.startswith("-"):
                    raw_amount = "-" + raw_amount
                elif direction == "OUT" and raw_amount.startswith("-"):
                    raw_amount = raw_amount.lstrip("-")

        tx: dict = {}
        tx["transactionId"] = transaction_id or self._next_tx_id()

        if direction == "OUT" and not omit_counterparty:
            tx["creditorName"] = counterparty_name or self._random_name()
            tx["creditorAccount"] = {"iban": counterparty_iban or self._random_iban()}
        elif direction == "IN" and not omit_counterparty:
            tx["debtorName"] = counterparty_name or self._random_name()
            tx["debtorAccount"] = {"iban": counterparty_iban or self._random_iban()}

        effective_currency = bad_currency if bad_currency is not None else currency
        if raw_amount is not None:
            tx["transactionAmount"] = {
                "currency": effective_currency,
                "amount": raw_amount,
            }
        elif not omit_amount:
            tx["transactionAmount"] = {
                "currency": effective_currency,
                "amount": self._random_amount(),
            }

        # bookingDate: only emit if we have a value (never emit null)
        if bd is not None:
            tx["bookingDate"] = bd.isoformat()

        if not omit_value_date:
            tx["valueDate"] = vd.isoformat()

        tx["remittanceInformationUnstructured"] = remittance or self._random_remittance(vd)
        tx["bankTransactionCode"] = self.rng.choice(BTC_CODES)

        return tx

    def generate_transactions_batch(
        self,
        account_iban: str,
        n_booked: int,
        n_pending: int,
        start_date: date,
        end_date: date,
        currency: str = "EUR",
        match_sign: bool = False,
    ) -> tuple[list[dict], list[dict]]:
        """Generate clean booked + pending transaction lists.

        match_sign: if True, raw amount sign matches direction (no INV-05).
        """
        booked = []
        for _ in range(n_booked):
            tx = self.generate_transaction(
                account_iban, start_date, end_date,
                include_booking_date=True, currency=currency,
                match_sign_to_direction=match_sign,
            )
            booked.append(tx)

        pending = []
        for _ in range(n_pending):
            tx = self.generate_transaction(
                account_iban, start_date, end_date,
                include_booking_date=False, currency=currency,
                match_sign_to_direction=match_sign,
            )
            pending.append(tx)

        booked.sort(key=lambda t: t.get("valueDate", ""))
        pending.sort(key=lambda t: t.get("valueDate", ""))

        return booked, pending


# ---------------------------------------------------------------------------
# Dataset definitions
# ---------------------------------------------------------------------------

def _build_accounts_json(accounts: list[dict]) -> dict:
    return {"accounts": accounts}


def _build_transactions_json(account_iban: str, booked: list, pending: list) -> dict:
    return {
        "account": {"iban": account_iban},
        "transactions": {
            "booked": booked,
            "pending": pending,
        },
    }


def generate_d1(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D1_synth_valid_small: small smoke-test, all valid, 0 drops, 0 WARNs → SUCCESS."""
    n_booked = n or 5
    n_pending = max(2, n_booked // 3)
    acct = gen.generate_account(country="DE", name="D1 Smoke Test Account")
    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
        match_sign=True,
    )
    return {
        "name": "D1_synth_valid_small",
        "description": "Clean happy-path smoke test. All transactions valid, amounts "
                        "sign-match direction, every required field present. "
                        "Adapter should produce SUCCESS with 0 drops and 0 WARNs.",
        "expected_outcome": "SUCCESS",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": 0,
            "variations": [],
        },
    }


def generate_d2(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D2_synth_mixed_large: large mixed set, pending without bookingDate,
    some sign/direction mismatches for INV-05 WARNs, drop=0."""
    n_booked = n or 50
    n_pending = max(15, n_booked // 3)
    acct = gen.generate_account(country="DE", name="D2 Mixed Large Account")

    # Generate baseline without sign matching — Berlin Group convention
    # (positive amounts regardless of direction), which triggers INV-05 WARNs
    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
    )

    # Inject deliberate INV-05 sign mismatches on IN transactions
    variations = []
    in_indices = [i for i, tx in enumerate(booked) if "debtorName" in tx]
    mismatch_indices = gen.rng.sample(in_indices, min(5, len(in_indices)))
    for idx in mismatch_indices:
        tx = booked[idx]
        amt = tx["transactionAmount"]["amount"]
        if not amt.startswith("-"):
            tx["transactionAmount"]["amount"] = "-" + amt
            variations.append(f"WARN_INV05: booked[{idx}] sign mismatch (IN with negative amount)")

    return {
        "name": "D2_synth_mixed_large",
        "description": "Large mixed dataset with natural Berlin Group sign convention "
                        "(positive amounts on OUT) causing INV-05 WARNs. Pending "
                        "transactions omit bookingDate. No drops expected.",
        "expected_outcome": "PARTIAL_SUCCESS",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": 0,
            "variations": variations,
        },
    }


def generate_d3(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D3_synth_valid_seed42: multi-account baseline, separate report file per account."""
    n_booked = n or 100
    n_pending = max(20, n_booked // 5)

    acct1 = gen.generate_account(country="DE", name="D3 Primary Account")
    acct2 = gen.generate_account(country="EE", currency="EUR", name="D3 Secondary Account")

    booked1, pending1 = gen.generate_transactions_batch(
        acct1["iban"], n_booked, n_pending, start_date, end_date,
        match_sign=True,
    )
    booked2, pending2 = gen.generate_transactions_batch(
        acct2["iban"], n_booked // 4, n_pending // 4, start_date, end_date,
        match_sign=True,
    )

    # Multi-account: each account gets its own report file (Berlin AIS convention).
    return {
        "name": "D3_synth_valid_seed42",
        "description": "Multi-account synthetic baseline with separate report files per account. "
                        "Two accounts (DE primary, EE secondary), each with its own "
                        "transactions file. Sign-matched amounts, no error injections.",
        "expected_outcome": "SUCCESS",
        "accounts": _build_accounts_json([acct1, acct2]),
        "transactions_files": {
            "transactions_1.json": _build_transactions_json(acct1["iban"], booked1, pending1),
            "transactions_2.json": _build_transactions_json(acct2["iban"], booked2, pending2),
        },
        "meta": {
            "n_booked": len(booked1) + len(booked2),
            "n_pending": len(pending1) + len(pending2),
            "n_booked_acct1": len(booked1),
            "n_pending_acct1": len(pending1),
            "n_booked_acct2": len(booked2),
            "n_pending_acct2": len(pending2),
            "expected_dropped": 0,
            "variations": [],
        },
    }


def generate_d4(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D4_synth_errors_seed42: targeted error injections E01–E04.
    4 transactions are invalid and should be DROPPED by the adapter.
    With default.yaml policy (fail_on: any_severity=ERROR, ratio_over_records=0.05),
    the drop ratio exceeds 5% → expected outcome is FAILED.
    """
    n_booked = n or 30
    n_pending = max(5, n_booked // 6)
    acct = gen.generate_account(country="DE", name="D4 Error Injection Account")

    # Generate clean baseline with sign matching
    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
        match_sign=True,
    )

    variations = []
    expected_dropped = 0

    # E01: invalid currency (violates ^[A-Z]{3}$ → ERROR-level DROP)
    e01 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        bad_currency="EURO",  # 4 chars, violates ^[A-Z]{3}$
        match_sign_to_direction=True,
        remittance="E01 invalid currency EURO",
    )
    booked.append(e01)
    variations.append("E01_INVALID_CURRENCY: currency='EURO' (4 chars) → ERROR DROP")
    expected_dropped += 1

    # E02: missing valueDate (C-01 maps directly from $.valueDate; no fallback → DROP)
    e02 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        omit_value_date=True,
        include_booking_date=False,
        match_sign_to_direction=True,
        remittance="E02 missing valueDate",
    )
    booked.append(e02)
    variations.append("E02_MISSING_VALUE_DATE: no valueDate → ERROR DROP")
    expected_dropped += 1

    # E03: unparseable amount (amount='not_a_number' → ERROR DROP)
    e03 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        bad_amount="not_a_number",
        remittance="E03 unparseable amount",
    )
    booked.append(e03)
    variations.append("E03_UNPARSEABLE_AMOUNT: amount='not_a_number' → ERROR DROP")
    expected_dropped += 1

    # E04: empty currency string (violates ^[A-Z]{3}$ → ERROR DROP)
    e04 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        bad_currency="",
        match_sign_to_direction=True,
        remittance="E04 empty currency",
    )
    booked.append(e04)
    variations.append("E04_EMPTY_CURRENCY: currency='' → ERROR DROP")
    expected_dropped += 1

    # Sanity check: drop ratio must exceed the 5% fail threshold
    total_records = len(booked) + len(pending)
    drop_ratio = expected_dropped / total_records
    if drop_ratio <= 0.05:
        raise ValueError(
            f"D4 sanity check failed: expected_dropped/total = "
            f"{expected_dropped}/{total_records} = {drop_ratio:.4f} <= 0.05. "
            f"Reduce baseline count or add more error injections."
        )

    return {
        "name": "D4_synth_errors_seed42",
        "description": "Targeted error injections (E01–E04) that each violate S-00B "
                        "schema constraints and produce ERROR-level drops. With 4 drops "
                        f"out of {total_records} records ({drop_ratio:.1%}), the drop ratio "
                        "exceeds the default.yaml threshold of 5%, so the adapter "
                        "outcome is FAILED.",
        "expected_outcome": "FAILED",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": expected_dropped,
            "variations": variations,
        },
    }


def generate_d5(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D5_synth_edges_seed99: edge cases that are schema-valid but borderline."""
    n_booked = n or 20
    n_pending = max(5, n_booked // 4)
    acct = gen.generate_account(country="DE", name="D5 Edge Cases Account")

    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
        match_sign=True,
    )

    variations = []

    # EDGE-01: zero amount
    edge01 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        amount_str="0.00",
        match_sign_to_direction=True,
        remittance="EDGE-01 zero amount",
    )
    booked.append(edge01)
    variations.append("EDGE-01_ZERO_AMOUNT: amount='0.00' — valid but semantically odd")

    # EDGE-02: very large amount (max precision 3 decimals per schema)
    edge02 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        amount_str="9999999.999",
        match_sign_to_direction=True,
        remittance="EDGE-02 large amount 3 decimal places",
    )
    booked.append(edge02)
    variations.append("EDGE-02_LARGE_AMOUNT: amount='9999999.999' — max precision")

    # EDGE-03: single digit amount (no decimals)
    edge03 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        amount_str="1",
        match_sign_to_direction=True,
        remittance="EDGE-03 integer amount no decimals",
    )
    booked.append(edge03)
    variations.append("EDGE-03_INTEGER_AMOUNT: amount='1' — valid per pattern ^-?\\d+(\\.\\d{1,3})?$")

    # EDGE-04: negative amount with creditorName (OUT, sign matches)
    edge04 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        direction="OUT",
        amount_str="-50.00",
        remittance="EDGE-04 negative amount OUT direction",
    )
    booked.append(edge04)
    variations.append("EDGE-04_NEGATIVE_OUT: amount='-50.00' + creditorName → OUT, sign matches, no INV-05")

    # EDGE-05: positive amount with debtorName (IN, sign matches)
    edge05 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        direction="IN",
        amount_str="100.50",
        remittance="EDGE-05 positive amount IN direction",
    )
    booked.append(edge05)
    variations.append("EDGE-05_POSITIVE_IN: amount='100.50' + debtorName → IN, no INV-05")

    # EDGE-06: same value_date and booking_date
    same_date = gen._random_date(start_date, end_date)
    edge06 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        value_date_str=same_date.isoformat(),
        booking_date_str=same_date.isoformat(),
        match_sign_to_direction=True,
        remittance="EDGE-06 same booking and value date",
    )
    booked.append(edge06)
    variations.append(f"EDGE-06_SAME_DATES: bookingDate == valueDate == {same_date.isoformat()}")

    # EDGE-07: very long remittance (valid, LLM projection truncates to 160)
    long_rem = "EDGE-07 " + "A" * 300
    edge07 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        match_sign_to_direction=True,
        remittance=long_rem,
    )
    booked.append(edge07)
    variations.append("EDGE-07_LONG_REMITTANCE: 308 chars — valid, LLM projection truncates to 160")

    # EDGE-08: no counterparty at all (QC-1 INFO)
    edge08 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        omit_counterparty=True,
        amount_str="-25.00",
        remittance="EDGE-08 no counterparty",
    )
    booked.append(edge08)
    variations.append("EDGE-08_NO_COUNTERPARTY: no creditor/debtor → direction by sign, QC-1 INFO")

    return {
        "name": "D5_synth_edges_seed99",
        "description": "Schema-valid edge cases testing boundary conditions: zero amount, "
                        "large amount, integer amount, sign conventions, same dates, long "
                        "remittance, and missing counterparty (QC-1 INFO).",
        "expected_outcome": "PARTIAL_SUCCESS",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": 0,
            "variations": variations,
        },
    }


def generate_d6(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D6_synth_dupes_seed99: tests INV-09 duplicate record_id detection.

    Exact copies produce the same record_id after mapping (same hash inputs).
    The adapter keeps the first occurrence deterministically and drops the rest
    with INV-09 WARN.  Near-duplicates (different amount/remittance/txId) produce
    different record_ids and are NOT dropped — they verify that the hash is
    sensitive to field changes.
    """
    n_booked = n or 15
    n_pending = max(3, n_booked // 5)
    acct = gen.generate_account(country="DE", name="D6 Duplicates Account")

    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
        match_sign=True,
    )

    variations = []
    expected_dropped = 0

    # DUP-01: exact duplicate of booked[0] — same record_id → INV-09 DROP
    if booked:
        original = booked[0]
        exact_dup = json.loads(json.dumps(original))  # deep copy
        booked.append(exact_dup)
        variations.append(f"DUP-01_EXACT: exact copy of booked[0] (transactionId={original['transactionId']}) → INV-09 DROP")
        expected_dropped += 1

    # DUP-02: second exact duplicate of booked[0] — same record_id → INV-09 DROP
    if booked:
        exact_dup2 = json.loads(json.dumps(booked[0]))
        booked.append(exact_dup2)
        variations.append(f"DUP-02_EXACT: second copy of booked[0] (transactionId={booked[0]['transactionId']}) → INV-09 DROP")
        expected_dropped += 1

    # DUP-03: exact duplicate of booked[1] — same record_id → INV-09 DROP
    if len(booked) > 1:
        original2 = booked[1]
        exact_dup3 = json.loads(json.dumps(original2))
        booked.append(exact_dup3)
        variations.append(f"DUP-03_EXACT: exact copy of booked[1] (transactionId={original2['transactionId']}) → INV-09 DROP")
        expected_dropped += 1

    # NEAR-01: same txId but different amount — different record_id → NOT dropped
    if len(booked) > 2:
        near1 = json.loads(json.dumps(booked[2]))
        near1["transactionAmount"]["amount"] = str(float(near1["transactionAmount"]["amount"]) + 0.01)
        booked.append(near1)
        variations.append(f"NEAR-01_DIFF_AMOUNT: same txId={near1['transactionId']}, amount differs → different record_id, kept")

    # NEAR-02: same fields except remittance — different record_id → NOT dropped
    near2_base = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        match_sign_to_direction=True,
        remittance="NEAR-02 original remittance",
    )
    near2_copy = json.loads(json.dumps(near2_base))
    near2_copy["remittanceInformationUnstructured"] = "NEAR-02 modified remittance"
    booked.append(near2_base)
    booked.append(near2_copy)
    variations.append(f"NEAR-02_DIFF_REMITTANCE: same txId={near2_base['transactionId']}, remittance differs → different record_id, both kept")

    return {
        "name": "D6_synth_dupes_seed99",
        "description": "Tests INV-09 duplicate record_id detection. Contains 3 exact "
                        "duplicates (same hash inputs → same record_id → dropped with "
                        "INV-09 WARN, keeping first deterministically) and 2 near-duplicates "
                        "(different amount or remittance → different record_id → kept). "
                        "Adapter should produce PARTIAL_SUCCESS with 3 INV-09 WARNs.",
        "expected_outcome": "PARTIAL_SUCCESS",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": expected_dropped,
            "variations": variations,
        },
    }


def generate_d8(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D8_load_test_10k_seed88: load test with 10 000 transactions.

    Tests that the pipeline handles production-scale volumes correctly:
    determinism is preserved, performance remains acceptable,
    and no memory or ordering issues emerge at scale.
    """
    n_booked = n or 8000
    n_pending = max(2000, n_booked // 4)
    acct = gen.generate_account(country="DE", name="D8 Load Test Account")

    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
        match_sign=True,
    )

    return {
        "name": "D8_load_test_10k_seed88",
        "description": "Load test with 10 000 transactions (8 000 booked + 2 000 pending). "
                        "Tests pipeline behaviour at production-scale volumes: determinism, "
                        "performance, memory handling, and sort stability. "
                        "All transactions are valid — expected outcome is SUCCESS.",
        "expected_outcome": "SUCCESS",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": 0,
            "variations": [],
        },
    }


def generate_d9(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D9_synth_perf_seed9: standard-scale performance dataset (~1 000 transactions).

    Represents a realistic 6-month bank statement for an active account
    (~5.5 transactions/day). Used to validate MF6 (≤ 500 ms for the standard
    test dataset) and to provide a third scaling data point between D3 (150 tx)
    and D8 (10 000 tx).
    All transactions are valid — expected outcome is SUCCESS.
    """
    n_booked = n or 800
    n_pending = max(200, n_booked // 4)
    acct = gen.generate_account(country="EE", name="D9 Standard Scale Account")

    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
        match_sign=True,
    )

    return {
        "name": "D9_synth_perf_seed9",
        "description": "Standard-scale performance dataset with ~1 000 transactions "
                        "(800 booked + 200 pending). Represents a realistic 6-month bank "
                        "statement (~5.5 tx/day). Validates MF6 (≤ 500 ms) and provides a "
                        "scaling data point between D3 (150 tx) and D8 (10 000 tx). "
                        "All transactions are valid — expected outcome is SUCCESS.",
        "expected_outcome": "SUCCESS",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": 0,
            "variations": [],
        },
    }


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

def _validate_single_report(name: str, filename: str, accounts_data: dict, tx_data: dict) -> list[str]:
    """Validate a single transaction report file against S-00B requirements."""
    warnings = []
    acct_ibans = {a["iban"] for a in accounts_data.get("accounts", [])}

    # C-01: account.iban must be present for account_resolution
    tx_account_iban = (tx_data.get("account") or {}).get("iban")
    if not tx_account_iban:
        warnings.append(f"{name}: {filename} missing account.iban (needed by C-01)")
    elif tx_account_iban not in acct_ibans:
        warnings.append(f"{name}: {filename} account.iban '{tx_account_iban}' not in accounts.json")

    # S-00B: each Tx
    tx_obj = tx_data.get("transactions", {})
    for status_key in ("booked", "pending"):
        for j, tx in enumerate(tx_obj.get(status_key, [])):
            path = f"{filename} $.transactions.{status_key}[{j}]"

            # Required: transactionAmount
            ta = tx.get("transactionAmount")
            if not ta:
                warnings.append(f"{name}: {path} missing transactionAmount")
            else:
                amt = ta.get("amount", "")
                if amt and not re.match(r"^-?\d+(\.\d{1,3})?$", amt):
                    warnings.append(f"{name}: {path} amount '{amt}' does not match pattern")
                cur = ta.get("currency", "")
                if not _currency_valid(cur):
                    warnings.append(f"{name}: {path} currency '{cur}' invalid")

            # Required: valueDate
            if not tx.get("valueDate"):
                warnings.append(f"{name}: {path} missing valueDate")

            # Pending should NOT have bookingDate
            if status_key == "pending" and "bookingDate" in tx:
                warnings.append(f"{name}: {path} pending tx has bookingDate (should omit)")

    return warnings


def validate_dataset(name: str, accounts_data: dict, tx_data_or_none: dict | None,
                     meta: dict, *, tx_files: dict | None = None) -> list[str]:
    """Validate generated data against S-00A / S-00B requirements.

    Supports both single-file (tx_data_or_none) and multi-file (tx_files) modes.
    """
    warnings = []

    # --- S-00A: accounts.json ---
    for i, acct in enumerate(accounts_data.get("accounts", [])):
        for field in ("resourceId", "iban", "currency"):
            if not acct.get(field):
                warnings.append(f"{name}: accounts[{i}] missing required '{field}'")
        iban = acct.get("iban", "")
        if not _iban_valid(iban):
            warnings.append(f"{name}: accounts[{i}].iban '{iban}' does not match S-00A pattern")
        cur = acct.get("currency", "")
        if not _currency_valid(cur):
            warnings.append(f"{name}: accounts[{i}].currency '{cur}' invalid")

    # --- S-00B: validate report file(s) ---
    if tx_files:
        # Multi-file mode (e.g. D3 with transactions_1.json, transactions_2.json)
        for filename in sorted(tx_files.keys()):
            warnings.extend(_validate_single_report(name, filename, accounts_data, tx_files[filename]))
    elif tx_data_or_none is not None:
        # Single-file mode (backward compatible)
        warnings.extend(_validate_single_report(name, "transactions.json", accounts_data, tx_data_or_none))

    return warnings


def _iban_valid(s: str) -> bool:
    return bool(re.match(r"^[A-Z]{2}[0-9A-Z]{13,32}$", s))


def _currency_valid(s: str) -> bool:
    return bool(re.match(r"^[A-Z]{3}$", s))


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_dataset(out_dir: Path, dataset: dict, seed: int, start_date: date, end_date: date) -> None:
    name = dataset["name"]
    folder = out_dir / name
    folder.mkdir(parents=True, exist_ok=True)

    accounts = dataset["accounts"]
    meta = dataset["meta"]

    # Determine single-file vs multi-file mode
    tx_files = dataset.get("transactions_files")  # multi-account support
    transactions = dataset.get("transactions")     # single-file (backward compatible)

    # Write JSON files (no meta embedded — meta goes only in README)
    with open(folder / "accounts.json", "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    if tx_files:
        # Multi-file: write each report file separately
        for filename in sorted(tx_files.keys()):
            with open(folder / filename, "w", encoding="utf-8") as f:
                json.dump(tx_files[filename], f, indent=2, sort_keys=True, ensure_ascii=False)
                f.write("\n")
    else:
        # Single-file (backward compatible)
        with open(folder / "transactions.json", "w", encoding="utf-8") as f:
            json.dump(transactions, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")

    # Quality gate
    warnings = validate_dataset(name, accounts, transactions, meta, tx_files=tx_files)

    # Build README
    description = dataset.get("description", "")
    expected_outcome = dataset.get("expected_outcome", "PARTIAL_SUCCESS")
    variations_list = "\n".join(f"  - `{v}`" for v in meta["variations"]) if meta["variations"] else "  (none)"

    # Properties table — show per-account breakdown for multi-file datasets
    props_rows = [
        f"| Seed | {seed} |",
        f"| Date range | {start_date.isoformat()} – {end_date.isoformat()} |",
        f"| Booked (total) | {meta['n_booked']} |",
        f"| Pending (total) | {meta['n_pending']} |",
    ]
    if tx_files:
        # Add per-account breakdowns if available
        for i, filename in enumerate(sorted(tx_files.keys()), 1):
            bk = meta.get(f"n_booked_acct{i}")
            pk = meta.get(f"n_pending_acct{i}")
            if bk is not None and pk is not None:
                acct_iban = tx_files[filename].get("account", {}).get("iban", "?")
                props_rows.append(f"| {filename} | {bk} booked + {pk} pending (iban: {acct_iban}) |")
    props_rows.extend([
        f"| Expected dropped | {meta['expected_dropped']} |",
        f"| Expected outcome | {expected_outcome} |",
    ])

    report_files_note = ""
    if tx_files:
        fnames = ", ".join(sorted(tx_files.keys()))
        report_files_note = f"\n**Report files:** {fnames}\n"

    readme = f"""# {name}

{description}
{report_files_note}
## Properties

| Property | Value |
|---|---|
{chr(10).join(props_rows)}

## What this dataset tests

{description}

## Variations / injected codes

{variations_list}

## Quality gate warnings

{"(none)" if not warnings else chr(10).join(f"- {w}" for w in warnings)}
"""
    with open(folder / "README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    # Print summary
    total = meta["n_booked"] + meta["n_pending"]
    print(f"  {name}: {total} total ({meta['n_booked']} booked + {meta['n_pending']} pending), "
          f"expected_dropped={meta['expected_dropped']}, expected_outcome={expected_outcome}, "
          f"quality_warnings={len(warnings)}")
    for w in warnings:
        print(f"    WARN: {w}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DATASET_GENERATORS = {
    "D1": (generate_d1, 1),
    "D2": (generate_d2, 2),
    "D3": (generate_d3, 42),
    "D4": (generate_d4, 42),
    "D5": (generate_d5, 99),
    "D6": (generate_d6, 99),
    "D8": (generate_d8, 88),
    "D9": (generate_d9, 9),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PSD2/Berlin Group AIS test datasets.")
    parser.add_argument("--out", default="datasets/", help="Output root directory (default: datasets/)")
    parser.add_argument("--seed", type=int, default=None, help="Override seed for all datasets")
    parser.add_argument("--dataset", default="all", help="D1|D2|D3|D4|D5|D6|all (default: all)")
    parser.add_argument("--n", type=int, default=None, help="Override transaction count")
    parser.add_argument("--start-date", default="2024-01-01", help="Start date (default: 2024-01-01)")
    parser.add_argument("--end-date", default="2024-12-31", help="End date (default: 2024-12-31)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)

    if args.dataset == "all":
        targets = list(DATASET_GENERATORS.keys())
    else:
        targets = [d.strip() for d in args.dataset.split(",")]

    print(f"Generating datasets: {', '.join(targets)}")
    print(f"Output: {out_dir.resolve()}")
    print(f"Date range: {start} – {end}")
    print()

    for key in targets:
        if key not in DATASET_GENERATORS:
            print(f"  SKIP: unknown dataset '{key}'")
            continue

        gen_fn, default_seed = DATASET_GENERATORS[key]
        seed = args.seed if args.seed is not None else default_seed
        gen = DatasetGenerator(seed)

        dataset = gen_fn(gen, start, end, args.n)
        write_dataset(out_dir, dataset, seed, start, end)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
