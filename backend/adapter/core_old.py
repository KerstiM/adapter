from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .io_excel import read_bank_excel
from .io_json import write_statement_json

import json
import io

def parse_estonian_csv_to_psd2(csv_content):
    # Loe CSV sisse
    df = pd.read_csv(io.StringIO(csv_content), sep=",")

    transactions = []

    for idx, row in df.iterrows():
        # 1. Määra tehingu suund (Credit/Debit)
        dc_indicator = row.get("Deebet/Kreedit (D/C)")
        amount_raw = float(row.get("Summa", 0))

        # PSD2 JSON-is on summa tavaliselt absoluutväärtus (positiivne string)
        amount_abs = abs(amount_raw)
        currency = row.get("Valuuta", "EUR")

        # Tehingu ID (kasutame 'Kande viide' või genereerime unikaalse)
        tx_id = str(row.get("Kande viide")) if not pd.isna(row.get("Kande viide")) else f"TX-{idx}"

        # Kuupäev
        booking_date = str(row.get("Kuupäev"))

        # Ehitame tehingu objekti
        tx = {
            "transactionId": tx_id,
            "bookingDate": booking_date,
            "valueDate": booking_date,  # Sinu CSV-s pole eraldi väärtuspäeva, kasutame sama
            "transactionAmount": {
                "amount": f"{amount_abs:.2f}",
                "currency": currency
            },
            # Selgitus läheb "remittanceInformationUnstructured" väljale
            "remittanceInformationUnstructured": str(row.get("Selgitus", "")).replace("\\", " "),
            # Kui on viitenumber, lisa see
            "remittanceInformationStructured": row.get("Viitenumber") if not pd.isna(row.get("Viitenumber")) else None
        }

        # 2. Lisa Debtor/Creditor info vastavalt suunale
        counterparty_name = row.get("Saaja/maksja nimi")
        counterparty_account = row.get("Saaja/maksja konto")  # Sinu näites on see tühi, aga kood peaks seda toetama

        if dc_indicator == "D":
            # Deebet (raha läheb välja) -> Sina oled Debtor, teine pool on Creditor
            # Pangakoodi järgi on see väljaminek
            tx["creditorName"] = counterparty_name
            if pd.isna(counterparty_account).empty:
                tx["creditorAccount"] = {"iban": counterparty_account}

            # Valikuline: lisa proprietary kood, et oleks selge, et see on väljaminek
            # tx["bankTransactionCode"] = "PMNT"

        elif dc_indicator == "C" or dc_indicator == "K":
            # Kreedit (raha tuleb sisse) -> Sina oled Creditor, teine pool on Debtor
            tx["debtorName"] = counterparty_name
            if pd.isna(counterparty_account).empty:
                tx["debtorAccount"] = {"iban": counterparty_account}

        # Eemalda tühjad väljad (None)
        tx = {k: v for k, v in tx.items() if v is not None}
        transactions.append(tx)

    # 3. Lõplik struktuur (Berlin Group)
    # Võtame konto numbri esimesest reast
    account_id = df.iloc[0]["Kliendi konto"] if not df.empty else "UNKNOWN"

    result = {
        "account": {
            "iban": account_id,
            "currency": "EUR"
        },
        "transactions": {
            "booked": transactions,
            "pending": []
        }
    }

    return result


# Käivita funktsioon
#psd2_json = parse_estonian_csv_to_psd2(csv_data)

# Prindi ilus JSON
#print(json.dumps(psd2_json, indent=2, ensure_ascii=False))

def build_transactions(
    df: pd.DataFrame,
    default_account_id: str,
    currency: str,
    iban: str
) -> List[Dict[str, Any]]:
    """
    Võtab bank.xlsx DataFrame'i ja ehitab sellest tehingute listi
    Berlin Group PSD2 openFinance struktuuris (camelCase, standardväljad).
    """
    transactions: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        # --- kuupäevad ---
        booking_raw = row.get("DATE")
        if pd.isna(booking_raw):
            continue  # jätame vahele, kui puudub broneeringu kuupäev

        booking_date = booking_raw.date() if hasattr(booking_raw, "date") else booking_raw
        value_raw = row.get("VALUE DATE")
        value_date = value_raw.date() if hasattr(value_raw, "date") else value_raw if not pd.isna(value_raw) else None

        # --- summade töötlus ---
        withdrawal_raw = row.get("WITHDRAWAL AMT", 0)
        deposit_raw = row.get("DEPOSIT AMT", 0)

        # --- kontrolli Nan väärtusi ja muuda NaN -> 0 ---
        withdrawal = float(0 if pd.isna(withdrawal_raw) else withdrawal_raw or 0)
        deposit = float(0 if pd.isna(deposit_raw) else deposit_raw or 0)

        if deposit > 0 and withdrawal == 0:
            transaction_type = "Credit"
            amount = deposit
        elif withdrawal > 0 and deposit == 0:
            transaction_type = "Debit"
            amount = -withdrawal
        else:
            continue  # rida ei ole üheselt määratav (mõlemad null või mõlemad täidetud)

        # --- saldo pärast tehingut ---
        balance_raw = row.get("BALANCE AMT")
        balance = float(balance_raw) if not pd.isna(balance_raw) else None

        # --- kontonumbri puhastamine (eemaldame Exceli ülakoma) ---
        account_raw = row.get("Account No", default_account_id)
        account_clean = str(account_raw).rstrip("'") if not pd.isna(account_raw) else default_account_id

        # --- Andmete puhastamine (et vältida JSON-i NaN väärtusi) ---
        counterparty_info = str(row.get("TRANSACTION DETAILS", "")).strip()
        entry_reference_raw = row.get("CHQ.NO.", None)
        entry_reference = str(entry_reference_raw) if not pd.isna(
            entry_reference_raw) and entry_reference_raw is not None else None

        # --- koosta PSD2-ülesehitusega transaktsiooniobjekt ---
        tx = {
            "rowIndex": idx,  # Hoia abiväljana
            "transactionId": f"{account_clean}-{booking_date}-{idx:06d}",
            "entryReference": entry_reference, # meta
            "transactionType": transaction_type, # meta
            "balanceAfterTransaction": { # meta
                "amount": f"{balance:.2f}" if balance is not None else None,
                "currency": currency
            },

            "transactionAmount": {
                "currency": currency,
                "amount": f"{abs(amount):.2f}"
            },
            "bookingDate": str(booking_date),
            "valueDate": str(value_date) if value_date else None,
            "remittanceInformationUnstructured": counterparty_info
        }

        # Vastavalt tehingu tüübile lisame Debtor/Creditor väljad:
        if transaction_type == "Credit":
            # Sissetulek (Debit tuleb sinu kontole). Vastaskonto on Debtor.
            tx["debtorName"] = counterparty_info  # Eeldame, et details sisaldab saatja nime
            tx["debtorAccount"] = {
                "iban": "NL76RABO0359400371"  # Vajaks saatja konto infot (IBAN)
            }
        elif transaction_type == "Debit":
            # Väljaminek (Credit läheb vastaskontole). Vastaskonto on Creditor.
            tx["creditorName"] = counterparty_info  # Eeldame, et details sisaldab saaja nime
            tx["creditorAccount"] = {
                "iban": "NL76RABO0359400371" # Vajaks saaja konto infot (IBAN)
            }

        transactions.append(tx)

    return transactions


def excel_statement_to_json(
    excel_path: str | Path,
    json_path: str | Path,
    account_id: str,
    currency: str = "EUR",
    institution: str = "SyntheticBank",
) -> None:
    # loe Excelist kontoväljavõte
    df = read_bank_excel(excel_path)
    # teisenda DataFrame -> PSD2-stiilis JSON transaktsioonid
    transactions = build_transactions(df, account_id, currency, iban)

    # Eeldame, et kõik Exceli tehingud on "broneeritud" (booked).
    # Ootel tehingute (pending) info puudub.

    # koosta PSD2 väljundobjekt
    result: Dict[str, Any] = {
        "account": {
            "accountId": account_id, # valikuline/meta
            "currency": currency, # valikuline/meta
            "iban": iban,
        },
        "statementPeriod": { # valikuline/meta
            "from": transactions[0]["bookingDate"] if transactions else None,
            "to": transactions[-1]["bookingDate"] if transactions else None,
        },
        "source": { # valikuline/meta
            "dataset": "kaggle_bank_statement",
            "schemaVersion": "v0"
        },
        "transactions": {
            "booked": transactions,
            "pending": pending,
            "_links": { # Lisaväljad võivad siia minna
                "account": {
                    "href": "/psd2/v1/accounts/3dc3d5b3-7023-4848-9853- f5400a64e80f"
                }
            }
        }
    }

    # salvesta JSON-faili
    write_statement_json(result, json_path)


def run_pipeline() -> None:
    """
    Main funktsioon lokaalseks testimiseks või käsurealt käivitamiseks.
    """
    excel_statement_to_json(
        excel_path="data/bank_test_2.csv",
        json_path="data/output.json",
        account_id="409000611074",
        currency="INR",
        institution="DemoBank",
    )
