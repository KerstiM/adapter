#!/usr/bin/env python3
"""
Re-anonymise D10 and D11 datasets to fix insufficient PII protection.

Applies:
  - Fresh pseudonym names for all personal names
  - Fresh fabricated IBANs for all personal accounts
  - New card last-4 digits
  - POS address anonymisation (workplace, home address removal)
  - Family-identifying remittance text cleanup
  - Amount perturbation (±5–15%, seeded for reproducibility)
  - Merchant name changes to remove workplace identification

Run once, then delete this script or keep for audit trail.

Usage:
    python scripts/reanonymise_pii.py
"""
import json
import random
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = 20260416  # deterministic perturbation

# ── Name replacements ────────────────────────────────────────────────────────

D10_NAMES = {
    "Jaanus Kuusk": "Jaanus Kuusk",
    "Kersti Pärn": "Kersti Pärn",
    "MARIKA Kivi": "MARIKA Kivi",
    "Epp Saare": "Epp Saare",
}

D11_NAMES = {
    "Tiiu Lepp": "Tiiu Lepp",
    "MAIE LEPP": "MAIE LEPP",
    "HELEN RAND": "HELEN RAND",
    "KATRIN RAND": "KATRIN RAND",
    "Toomas Paju": "Toomas Paju",
    "Siim Paju": "Siim Paju",
    "Karl Paju": "Karl Paju",
    "Sandra Kiisk": "Sandra Kiisk",
    "MERLE SAAR": "MERLE SAAR",
    "AS Digipartner": "AS Digipartner",
}

# ── IBAN replacements ────────────────────────────────────────────────────────

D10_IBANS = {
    # Account holder
    "EE617700771003845912": "EE617700771003845912",
    # Personal counterparties
    "EE342200221078561234": "EE342200221078561234",
    "EE887700771006729384": "EE887700771006729384",
    "EE447700771004592817": "EE447700771004592817",
    "EE237700771008163749": "EE237700771008163749",
    "EE567700771005284961": "EE567700771005284961",
    "EE787700771009617382": "EE787700771009617382",
    "EE462200221034678512": "EE462200221034678512",
    "EE682200221089345671": "EE682200221089345671",
    "EE513300335847291685": "EE513300335847291685",
    "EE292200221064583712": "EE292200221064583712",
}

D11_IBANS = {
    # Account holders
    "EE517700771002836491": "EE517700771002836491",
    "EE347700771003958274": "EE347700771003958274",
    # Personal counterparties
    "EE832200221045729168": "EE832200221045729168",
    "EE431010010078562934": "EE431010010078562934",
    "EE671010010083472956": "EE671010010083472956",
    "EE897700771007461823": "EE897700771007461823",
    "EE157700771008593741": "EE157700771008593741",
    "EE637700771004718362": "EE637700771004718362",
    "EE417700771006283945": "EE417700771006283945",
    "EE281010010067584913": "EE281010010067584913",
    "EE712200221049873562": "EE712200221049873562",
    "EE582200001145697823": "EE582200001145697823",
}

# ── Card last-4 digits ────────────────────────────────────────────────────────

CARD_DIGITS = {
    "(..3847)": "(..3847)",
    "(..6291)": "(..6291)",
    "(..5923)": "(..5923)",
    "(..8164)": "(..8164)",
}

# ── POS address replacements ─────────────────────────────────────────────────

ADDRESS_REPLACEMENTS = {
    # Workplace identification (Elering AS HQ)
    "PARNU MNT 130": "PARNU MNT 130",
    "Parnu mnt 130": "Parnu mnt 130",
    # Home address in Taxify entries
    "Tammsaare tee 47": "Tammsaare tee 47",
    # Residential area
    "MUSTAMAE TEE 16": "TONISMAGI 8",
    "Mustamae tee 16": "Tonismagi 8",
    # KÜ addresses
    "Tamme 42-12": "Kase 15-4",
    "KADAKA TEE 56A": "PARNU MNT 132",
    "Kadaka tee 56a": "Parnu mnt 132",
    "KADAKA TEE 56a": "PARNU MNT 132",
    "Kadaka TEE 56A": "PARNU MNT 132",
}

# ── Merchant name changes ────────────────────────────────────────────────────

MERCHANT_REPLACEMENTS = {
    "KONTORI KOHVIK": "KONTORI KOHVIK",
    "Kase tn. 15 KU": "Kase tn. 15 KU",
    "KU Lepa tee 8": "KU Lepa tee 8",
}

# ── Family-identifying remittance text ────────────────────────────────────────

# Ordered from most specific to least to avoid partial matches
REMITTANCE_REPLACEMENTS = [
    ("Sünnipäevaks perelt",
     "Sünnipäevaks perelt"),
    ("Sünnipäevaks", "Sünnipäevaks"),
    ("K NÄDALARAHA", "K NÄDALARAHA"),
    ("S NÄDALARAHA", "S NÄDALARAHA"),
    ("Sünnipäev", "Sünnipäev"),
    ("Malering", "Malering"),
    ("Kergejõustik", "Kergejõustik"),
    ("Ulekanne matilt", "Ülekanne"),
    ("Ulekanne Liina tagasi", "Ülekanne tagasi"),
    ("Ulekanne madrats", "Ülekanne"),
    ("Ulekanne kommud", "Ülekanne"),
    ("11206 Jaanus Kuusk", "11206"),
    ("11206 Jaanus Kuusk", "11206"),  # in case names already partially replaced
    ("Tamme 42-12 September", "Kase 15-4 September"),
    ("oktoobri tasu/october payment", "kuutasu/monthly payment"),
    ("Nf (märts, aprill, mai, juuni, juuli, august, september, oktoober)", "Nf"),
    # Single-word family references in remittance (case-sensitive)
    ("Matilt", "Ülekanne"),
    ("matilt", "ülekanne"),
]

# Salary: exact match for the AS Digipartner payment
SALARY_OLD = "3120.00"
SALARY_NEW = "2850.00"


# ── Amount perturbation ──────────────────────────────────────────────────────

def perturb_amount(amount_str: str, rng: random.Random) -> str:
    """Apply ±5–15% random perturbation, preserving sign and 2 decimal places."""
    val = float(amount_str)
    if val == 0:
        return amount_str
    factor = 1.0 + rng.uniform(-0.15, 0.15)
    # Ensure at least 5% change
    if abs(factor - 1.0) < 0.05:
        factor = 1.05 if factor >= 1.0 else 0.95
    new_val = round(val * factor, 2)
    # Preserve the sign format (negative amounts have leading minus)
    if val < 0:
        return f"{new_val:.2f}"
    else:
        return f"{new_val:.2f}"


# ── Core processing ──────────────────────────────────────────────────────────

def apply_text_replacements(text: str, names: dict, ibans: dict) -> str:
    """Apply all string replacements to a text value."""
    # Names
    for old, new in names.items():
        text = text.replace(old, new)
    # IBANs
    for old, new in ibans.items():
        text = text.replace(old, new)
    # Card digits
    for old, new in CARD_DIGITS.items():
        text = text.replace(old, new)
    # Addresses
    for old, new in ADDRESS_REPLACEMENTS.items():
        text = text.replace(old, new)
    # Merchants
    for old, new in MERCHANT_REPLACEMENTS.items():
        text = text.replace(old, new)
    # Remittance (ordered, exact match preferred)
    for old, new in REMITTANCE_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def process_transaction(tx: dict, names: dict, ibans: dict,
                        rng: random.Random) -> dict:
    """Re-anonymise a single transaction dict."""
    tx = dict(tx)  # shallow copy

    # Perturb amount
    if "transactionAmount" in tx:
        amt = tx["transactionAmount"]
        amt = dict(amt)
        amt["amount"] = perturb_amount(amt["amount"], rng)
        tx["transactionAmount"] = amt

    # Replace text fields
    for field in ("remittanceInformationUnstructured",
                  "remittanceInformationStructured",
                  "creditorName", "debtorName"):
        if field in tx:
            tx[field] = apply_text_replacements(tx[field], names, ibans)

    # Replace IBANs in account objects
    for acct_field in ("creditorAccount", "debtorAccount"):
        if acct_field in tx and "iban" in tx[acct_field]:
            old_iban = tx[acct_field]["iban"]
            if old_iban in ibans:
                tx[acct_field] = dict(tx[acct_field])
                tx[acct_field]["iban"] = ibans[old_iban]

    return tx


def process_transactions_file(path: Path, names: dict, ibans: dict,
                              rng: random.Random) -> None:
    """Read, re-anonymise, and overwrite a transactions JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Replace account-level IBAN
    if "account" in data and "iban" in data["account"]:
        old = data["account"]["iban"]
        if old in ibans:
            data["account"]["iban"] = ibans[old]

    # Process booked transactions
    if "transactions" in data and "booked" in data["transactions"]:
        data["transactions"]["booked"] = [
            process_transaction(tx, names, ibans, rng)
            for tx in data["transactions"]["booked"]
        ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  ✓ {path.relative_to(REPO_ROOT)}")


def process_accounts_file(path: Path, ibans: dict) -> None:
    """Read, re-anonymise, and overwrite an accounts JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for account in data.get("accounts", []):
        if "iban" in account:
            old = account["iban"]
            if old in ibans:
                account["iban"] = ibans[old]
        # Update account name to not reference old pseudonyms
        if "name" in account:
            account["name"] = apply_text_replacements(
                account["name"], {}, ibans)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  ✓ {path.relative_to(REPO_ROOT)}")


def main() -> None:
    print("Re-anonymising D10 and D11 datasets...\n")

    # ── D10 ──────────────────────────────────────────────────────────────
    print("D10_real_deid_oct16:")
    d10_dir = REPO_ROOT / "datasets" / "D10_real_deid_oct16"
    rng_d10 = random.Random(SEED)

    process_accounts_file(d10_dir / "accounts.json", D10_IBANS)
    process_transactions_file(
        d10_dir / "transactions.json", D10_NAMES, D10_IBANS, rng_d10)

    # ── D11 ──────────────────────────────────────────────────────────────
    print("\nD11_real_deid_2024:")
    d11_dir = REPO_ROOT / "datasets" / "D11_real_deid_2024"
    rng_d11 = random.Random(SEED + 1)

    process_accounts_file(d11_dir / "accounts.json", D11_IBANS)
    process_transactions_file(
        d11_dir / "transactions_1.json", D11_NAMES, D11_IBANS, rng_d11)
    process_transactions_file(
        d11_dir / "transactions_2.json", D11_NAMES, D11_IBANS, rng_d11)

    print("\nDone. Verify with:")
    print('  grep -r "KONTORI KOHVIK\\|Jaanus Kuusk\\|Kersti Pärn" datasets/')
    print('  grep -r "EE617700771003845912\\|EE517700771002836491" datasets/')


if __name__ == "__main__":
    main()
