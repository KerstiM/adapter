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
    "Marten Koppel": "Jaanus Kuusk",
    "Liina Rebane": "Kersti Pärn",
    "KADRI Lepik": "MARIKA Kivi",
    "Mari Tamm": "Epp Saare",
}

D11_NAMES = {
    "Ana Tamm": "Tiiu Lepp",
    "LIINA TAMM": "MAIE LEPP",
    "KRISTEL KASK": "HELEN RAND",
    "PIRET KASK": "KATRIN RAND",
    "Mart Mägi": "Toomas Paju",
    "Riku Mägi": "Siim Paju",
    "Kaspar Mägi": "Karl Paju",
    "Annika Lepik": "Sandra Kiisk",
    "JAANIKA KUKK": "MERLE SAAR",
    "AS Tehnogrupp": "AS Digipartner",
}

# ── IBAN replacements ────────────────────────────────────────────────────────

D10_IBANS = {
    # Account holder
    "EE387700771001292847": "EE617700771003845912",
    # Personal counterparties
    "EE192200221056439871": "EE342200221078561234",
    "EE467700771009183456": "EE887700771006729384",
    "EE527700771003847261": "EE447700771004592817",
    "EE617700771007293845": "EE237700771008163749",
    "EE747700771002938471": "EE567700771005284961",
    "EE827700771008461293": "EE787700771009617382",
    "EE222200221045839271": "EE462200221034678512",
    "EE552200221067128934": "EE682200221089345671",
    "EE363300335812478956": "EE513300335847291685",
    "EE482200221098127643": "EE292200221064583712",
}

D11_IBANS = {
    # Account holders
    "EE387700771001449271": "EE517700771002836491",
    "EE127700771001384912": "EE347700771003958274",
    # Personal counterparties
    "EE672200221010384902": "EE832200221045729168",
    "EE791010010043384918": "EE431010010078562934",
    "EE201010010409384918": "EE671010010083472956",
    "EE577700771002384960": "EE897700771007461823",
    "EE937700771001384940": "EE157700771008593741",
    "EE207700771005384950": "EE637700771004718362",
    "EE687700771001384930": "EE417700771006283945",
    "EE041010010433384915": "EE281010010067584913",
    "EE502200221015384969": "EE712200221049873562",
    "EE322200001120384980": "EE582200001145697823",
}

# ── Card last-4 digits ────────────────────────────────────────────────────────

CARD_DIGITS = {
    "(..7821)": "(..3847)",
    "(..4536)": "(..6291)",
    "(..9786)": "(..5923)",
    "(..4271)": "(..8164)",
}

# ── POS address replacements ─────────────────────────────────────────────────

ADDRESS_REPLACEMENTS = {
    # Workplace identification (Elering AS HQ)
    "KADAKA TEE 42": "PARNU MNT 130",
    "Kadaka tee 42": "Parnu mnt 130",
    # Home address in Taxify entries
    "Altmetsa poik 1": "Tammsaare tee 47",
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
    "ELERINGI KOHVIK": "KONTORI KOHVIK",
    "Tamme tn. 42 KU": "Kase tn. 15 KU",
    "KU Kase tee 23": "KU Lepa tee 8",
}

# ── Family-identifying remittance text ────────────────────────────────────────

# Ordered from most specific to least to avoid partial matches
REMITTANCE_REPLACEMENTS = [
    ("Rikule 8. sünnipaevaks  Tädi Piret, onu Kert ja väike Orm",
     "Sünnipäevaks perelt"),
    ("Rikule 8.ndaks sünnipäevaks", "Sünnipäevaks"),
    ("Jasper NÄDALARAHA", "K NÄDALARAHA"),
    ("Ruben NÄDALARAHA", "S NÄDALARAHA"),
    ("Riku sünnipäev", "Sünnipäev"),
    ("Riku malering", "Malering"),
    ("Riku kergejõustik", "Kergejõustik"),
    ("Ulekanne matilt", "Ülekanne"),
    ("Ulekanne Liina tagasi", "Ülekanne tagasi"),
    ("Ulekanne madrats", "Ülekanne"),
    ("Ulekanne kommud", "Ülekanne"),
    ("11206 Marten Koppel", "11206"),
    ("11206 Jaanus Kuusk", "11206"),  # in case names already partially replaced
    ("Tamme 42-12 September", "Kase 15-4 September"),
    ("oktoobri tasu/october payment", "kuutasu/monthly payment"),
    ("Nf (märts, aprill, mai, juuni, juuli, august, september, oktoober)", "Nf"),
    # Single-word family references in remittance (case-sensitive)
    ("Matilt", "Ülekanne"),
    ("matilt", "ülekanne"),
]

# Salary: exact match for the AS Tehnogrupp payment
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
    print("D10_real_anon_oct16:")
    d10_dir = REPO_ROOT / "datasets" / "D10_real_anon_oct16"
    rng_d10 = random.Random(SEED)

    process_accounts_file(d10_dir / "accounts.json", D10_IBANS)
    process_transactions_file(
        d10_dir / "transactions.json", D10_NAMES, D10_IBANS, rng_d10)

    # ── D11 ──────────────────────────────────────────────────────────────
    print("\nD11_real_anon_2024:")
    d11_dir = REPO_ROOT / "datasets" / "D11_real_anon_2024"
    rng_d11 = random.Random(SEED + 1)

    process_accounts_file(d11_dir / "accounts.json", D11_IBANS)
    process_transactions_file(
        d11_dir / "transactions_1.json", D11_NAMES, D11_IBANS, rng_d11)
    process_transactions_file(
        d11_dir / "transactions_2.json", D11_NAMES, D11_IBANS, rng_d11)

    print("\nDone. Verify with:")
    print('  grep -r "ELERINGI KOHVIK\\|Marten Koppel\\|Liina Rebane" datasets/')
    print('  grep -r "EE387700771001292847\\|EE387700771001449271" datasets/')


if __name__ == "__main__":
    main()
