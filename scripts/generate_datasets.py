#!/usr/bin/env python3
"""
Generate deterministic PSD2/Berlin Group AIS test datasets D1–D6.

Each dataset produces:
  datasets/<name>/accounts.json
  datasets/<name>/transactions.json
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
    ) -> dict:
        iban = self._random_iban(country)
        return {
            "resourceId": resource_id or uuid.UUID(int=self.rng.getrandbits(128), version=4).hex,
            "iban": iban,
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
        counterparty_name: str | None = None,
        counterparty_iban: str | None = None,
        omit_counterparty: bool = False,
        transaction_id: str | None = None,
        remittance: str | None = None,
    ) -> dict:
        """Generate a single Berlin AIS transaction."""
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

        # Sign: Berlin Group convention — amount is typically unsigned,
        # but some banks send negative for outgoing.
        # For IN: positive amount, debtorName present
        # For OUT: positive amount, creditorName present
        # force_sign_mismatch: send negative for IN (or positive OUT without creditor)
        if force_sign_mismatch and raw_amount and not raw_amount.startswith("-"):
            raw_amount = "-" + raw_amount

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
    ) -> tuple[list[dict], list[dict]]:
        """Generate clean booked + pending transaction lists."""
        booked = []
        for _ in range(n_booked):
            tx = self.generate_transaction(
                account_iban, start_date, end_date,
                include_booking_date=True, currency=currency,
            )
            booked.append(tx)

        pending = []
        for _ in range(n_pending):
            tx = self.generate_transaction(
                account_iban, start_date, end_date,
                include_booking_date=False, currency=currency,
            )
            pending.append(tx)

        # Sort booked by valueDate for realism
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
    """D1_public_valid_small: small smoke-test, all valid, drop=0."""
    n_booked = n or 5
    n_pending = max(2, n_booked // 3)
    acct = gen.generate_account(country="DE", name="D1 Smoke Test Account")
    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
    )
    return {
        "name": "D1_public_valid_small",
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
    """D2_public_mixed_large: large mixed set, pending without bookingDate,
    some sign/direction mismatches for INV-05 WARNs, drop=0."""
    n_booked = n or 50
    n_pending = max(15, n_booked // 3)
    acct = gen.generate_account(country="DE", name="D2 Mixed Large Account")

    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
    )

    # Inject INV-05 sign mismatches on ~10% of booked transactions
    variations = []
    mismatch_indices = gen.rng.sample(range(len(booked)), min(5, len(booked)))
    for idx in mismatch_indices:
        tx = booked[idx]
        amt = tx["transactionAmount"]["amount"]
        if not amt.startswith("-"):
            # creditorName present (OUT direction) but amount is positive → INV-05 WARN
            # This is actually the normal Berlin Group case, adapter already handles it.
            # To trigger INV-05: debtorName present (IN) but negative amount
            if "debtorName" in tx:
                tx["transactionAmount"]["amount"] = "-" + amt
                variations.append(f"WARN_INV05: booked[{idx}] sign mismatch (IN with negative amount)")

    return {
        "name": "D2_public_mixed_large",
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
    """D3_synth_valid_seed42: synthetic baseline, 0 error injections."""
    n_booked = n or 100
    n_pending = max(20, n_booked // 5)

    acct1 = gen.generate_account(country="DE", name="D3 Primary Account")
    acct2 = gen.generate_account(country="EE", currency="EUR", name="D3 Secondary Account")

    booked1, pending1 = gen.generate_transactions_batch(
        acct1["iban"], n_booked, n_pending, start_date, end_date,
    )
    booked2, pending2 = gen.generate_transactions_batch(
        acct2["iban"], n_booked // 4, n_pending // 4, start_date, end_date,
    )

    # Two separate transactions.json files would need multi-file support,
    # but the generator produces one file per dataset. We combine into one account's file.
    # OPEN QUESTION: adapter loads transactions.json per dataset folder, one file.
    # For multi-account, we use account1's iban in the transactions file.
    all_booked = booked1 + booked2
    all_pending = pending1 + pending2
    all_booked.sort(key=lambda t: t.get("valueDate", ""))
    all_pending.sort(key=lambda t: t.get("valueDate", ""))

    return {
        "name": "D3_synth_valid_seed42",
        "accounts": _build_accounts_json([acct1, acct2]),
        "transactions": _build_transactions_json(acct1["iban"], all_booked, all_pending),
        "meta": {
            "n_booked": len(all_booked),
            "n_pending": len(all_pending),
            "expected_dropped": 0,
            "variations": [],
        },
    }


def generate_d4(gen: DatasetGenerator, start_date: date, end_date: date, n: int | None) -> dict:
    """D4_synth_errors_seed42: targeted error injections E01–E06.
    Some transactions should be DROPPED by the adapter.
    """
    n_booked = n or 30
    n_pending = max(5, n_booked // 6)
    acct = gen.generate_account(country="DE", name="D4 Error Injection Account")

    # Generate a clean baseline
    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
    )

    variations = []
    expected_dropped = 0

    # E01: invalid currency (INV-01 → DROP)
    e01 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        bad_currency="EURO",  # 4 chars, violates ^[A-Z]{3}$
        remittance="E01 invalid currency EURO",
    )
    booked.append(e01)
    variations.append("E01_INVALID_CURRENCY: currency='EURO' (4 chars) → INV-01 DROP")
    expected_dropped += 1

    # E02: missing valueDate (no bookingDate fallback → DROP)
    e02 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        omit_value_date=True,
        include_booking_date=False,
        remittance="E02 missing valueDate no fallback",
    )
    booked.append(e02)
    variations.append("E02_MISSING_VALUE_DATE: no valueDate, no bookingDate → mapping DROP")
    expected_dropped += 1

    # E03: unparseable amount (INV-03 → DROP)
    e03 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        bad_amount="not_a_number",
        remittance="E03 unparseable amount",
    )
    booked.append(e03)
    variations.append("E03_UNPARSEABLE_AMOUNT: amount='not_a_number' → mapping DROP (parse failure)")
    expected_dropped += 1

    # E04: empty currency string (INV-01 → DROP)
    e04 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        bad_currency="",
        remittance="E04 empty currency",
    )
    booked.append(e04)
    variations.append("E04_EMPTY_CURRENCY: currency='' → INV-01 DROP")
    expected_dropped += 1

    # E05: missing valueDate WITH bookingDate fallback → should NOT drop (fallback applies)
    e05 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        omit_value_date=True,
        include_booking_date=True,
        remittance="E05 missing valueDate with bookingDate fallback",
    )
    booked.append(e05)
    variations.append("E05_VALUE_DATE_FALLBACK: no valueDate, has bookingDate → MAP-01 WARN, no drop")

    # E06: lowercase currency (INV-01 → DROP since schema pattern is ^[A-Z]{3}$)
    e06 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        bad_currency="eur",
        remittance="E06 lowercase currency",
    )
    booked.append(e06)
    variations.append("E06_LOWERCASE_CURRENCY: currency='eur' → pipeline uppercases it, valid after normalize")
    # Note: pipeline does .upper() on currency, so 'eur' → 'EUR' and passes INV-01.
    # This is NOT a drop — it's handled by the adapter normalization.

    return {
        "name": "D4_synth_errors_seed42",
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
    )

    variations = []

    # EDGE01: zero amount
    edge01 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        amount_str="0.00",
        remittance="EDGE01 zero amount",
    )
    booked.append(edge01)
    variations.append("EDGE01_ZERO_AMOUNT: amount='0.00' — valid but semantically odd")

    # EDGE02: very large amount (max precision 3 decimals per schema)
    edge02 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        amount_str="9999999.999",
        remittance="EDGE02 large amount 3 decimal places",
    )
    booked.append(edge02)
    variations.append("EDGE02_LARGE_AMOUNT: amount='9999999.999' — max precision")

    # EDGE03: single digit amount
    edge03 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        amount_str="1",
        remittance="EDGE03 integer amount no decimals",
    )
    booked.append(edge03)
    variations.append("EDGE03_INTEGER_AMOUNT: amount='1' — valid per pattern ^-?\\d+(\\.\\d{1,3})?$")

    # EDGE04: negative amount with creditorName (OUT direction, sign matches)
    edge04 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        direction="OUT",
        amount_str="-50.00",
        remittance="EDGE04 negative amount OUT direction",
    )
    booked.append(edge04)
    variations.append("EDGE04_NEGATIVE_OUT: amount='-50.00' + creditorName → OUT, sign matches, no INV-05")

    # EDGE05: positive amount with debtorName (IN direction, sign matches) — no warn
    edge05 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        direction="IN",
        amount_str="100.50",
        remittance="EDGE05 positive amount IN direction",
    )
    booked.append(edge05)
    variations.append("EDGE05_POSITIVE_IN: amount='100.50' + debtorName → IN, no INV-05")

    # EDGE06: same value_date and booking_date
    same_date = gen._random_date(start_date, end_date)
    edge06 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        value_date_str=same_date.isoformat(),
        booking_date_str=same_date.isoformat(),
        remittance="EDGE06 same booking and value date",
    )
    booked.append(edge06)
    variations.append(f"EDGE06_SAME_DATES: bookingDate == valueDate == {same_date.isoformat()}")

    # EDGE07: very long remittance (valid, just long)
    long_rem = "EDGE07 " + "A" * 300
    edge07 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        remittance=long_rem,
    )
    booked.append(edge07)
    variations.append("EDGE07_LONG_REMITTANCE: 307 chars — valid, LLM projection truncates to 160")

    # EDGE08: no counterparty at all (INV-10 WARN)
    edge08 = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        omit_counterparty=True,
        amount_str="-25.00",
        remittance="EDGE08 no counterparty",
    )
    booked.append(edge08)
    variations.append("EDGE08_NO_COUNTERPARTY: no creditor/debtor → direction by sign, INV-10 WARN")

    return {
        "name": "D5_synth_edges_seed99",
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
    """D6_synth_dupes_seed99: exact and near-duplicate transactions."""
    n_booked = n or 15
    n_pending = max(3, n_booked // 5)
    acct = gen.generate_account(country="DE", name="D6 Duplicates Account")

    booked, pending = gen.generate_transactions_batch(
        acct["iban"], n_booked, n_pending, start_date, end_date,
    )

    variations = []

    # DUP01: exact duplicate (same transactionId, same everything)
    if booked:
        original = booked[0]
        exact_dup = json.loads(json.dumps(original))  # deep copy
        booked.append(exact_dup)
        variations.append(f"DUP01_EXACT: exact copy of booked[0] (transactionId={original['transactionId']})")

    # DUP02: same transactionId but different amount (near-dupe)
    if len(booked) > 1:
        base = json.loads(json.dumps(booked[1]))
        base["transactionAmount"]["amount"] = str(float(base["transactionAmount"]["amount"]) + 0.01)
        booked.append(base)
        variations.append(f"DUP02_NEAR_AMOUNT: same txId={base['transactionId']}, amount differs by 0.01")

    # DUP03: same amount/date but different transactionId (structural near-dupe)
    if len(booked) > 2:
        base = json.loads(json.dumps(booked[2]))
        base["transactionId"] = gen._next_tx_id()
        booked.append(base)
        variations.append(f"DUP03_NEAR_TXID: same content, different transactionId={base['transactionId']}")

    # DUP04: same fields except remittance
    dup04_base = gen.generate_transaction(
        acct["iban"], start_date, end_date,
        remittance="DUP04 original remittance",
    )
    dup04_copy = json.loads(json.dumps(dup04_base))
    dup04_copy["remittanceInformationUnstructured"] = "DUP04 modified remittance"
    booked.append(dup04_base)
    booked.append(dup04_copy)
    variations.append(f"DUP04_NEAR_REMITTANCE: same txId={dup04_base['transactionId']}, remittance differs")

    return {
        "name": "D6_synth_dupes_seed99",
        "accounts": _build_accounts_json([acct]),
        "transactions": _build_transactions_json(acct["iban"], booked, pending),
        "meta": {
            "n_booked": len(booked),
            "n_pending": len(pending),
            "expected_dropped": 0,
            "variations": variations,
        },
    }


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

def validate_dataset(name: str, accounts_data: dict, tx_data: dict, meta: dict) -> list[str]:
    """Minimal quality checks: required fields per S-00A / S-00B."""
    warnings = []

    # S-00A checks
    for i, acct in enumerate(accounts_data.get("accounts", [])):
        for field in ("resourceId", "iban", "currency"):
            if not acct.get(field):
                warnings.append(f"{name}: accounts[{i}] missing required '{field}'")
        iban = acct.get("iban", "")
        if not _iban_valid(iban):
            warnings.append(f"{name}: accounts[{i}].iban '{iban}' does not match pattern")
        cur = acct.get("currency", "")
        if not _currency_valid(cur):
            warnings.append(f"{name}: accounts[{i}].currency '{cur}' invalid")

    # S-00B checks
    tx_obj = tx_data.get("transactions", {})
    for status_key in ("booked", "pending"):
        for j, tx in enumerate(tx_obj.get(status_key, [])):
            path = f"$.transactions.{status_key}[{j}]"

            # Required: transactionAmount
            ta = tx.get("transactionAmount")
            if not ta:
                warnings.append(f"{name}: {path} missing transactionAmount")
            else:
                if not ta.get("amount"):
                    warnings.append(f"{name}: {path} missing transactionAmount.amount")
                if not _currency_valid(ta.get("currency", "")):
                    # Deliberate error datasets may have bad currency
                    pass

            # Required: valueDate
            if not tx.get("valueDate"):
                # May be deliberate (error datasets)
                pass

    return warnings


def _iban_valid(s: str) -> bool:
    import re
    return bool(re.match(r"^[A-Z]{2}[0-9A-Z]{13,32}$", s))


def _currency_valid(s: str) -> bool:
    import re
    return bool(re.match(r"^[A-Z]{3}$", s))


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_dataset(out_dir: Path, dataset: dict, seed: int, start_date: date, end_date: date) -> None:
    name = dataset["name"]
    folder = out_dir / name
    folder.mkdir(parents=True, exist_ok=True)

    accounts = dataset["accounts"]
    transactions = dataset["transactions"]
    meta = dataset["meta"]

    # Write JSON files
    with open(folder / "accounts.json", "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    with open(folder / "transactions.json", "w", encoding="utf-8") as f:
        json.dump(transactions, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    # Quality gate
    warnings = validate_dataset(name, accounts, transactions, meta)

    # Write README.md
    variations_list = "\n".join(f"  - `{v}`" for v in meta["variations"]) if meta["variations"] else "  (none)"
    readme = f"""# {name}

| Property | Value |
|---|---|
| Seed | {seed} |
| Date range | {start_date.isoformat()} – {end_date.isoformat()} |
| Booked | {meta['n_booked']} |
| Pending | {meta['n_pending']} |
| Expected dropped | {meta['expected_dropped']} |

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
          f"expected_dropped={meta['expected_dropped']}, quality_warnings={len(warnings)}")
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
