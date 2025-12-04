import pandas as pd
import json
from pathlib import Path
from typing import Any, Dict


# --- ABIFUNKTSIOONID ---

def _parse_amount(value: Any) -> float:
    """Summa parsimine, tagastab 0.0 vea korral."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _get_transaction_id(row: pd.Series, idx: int) -> str:
    """Leiab kande viite või genereerib unikaalse ID."""
    val = row.get("Kande viide")
    return str(val) if not pd.isna(val) else f"TX-{idx:06d}"


def _add_counterparty_details(tx: Dict[str, Any], row: pd.Series) -> None:
    """Lisab tehingule Debtor või Creditor info vastavalt D/C indikaatorile."""
    dc_indicator = row.get("Deebet/Kreedit (D/C)")
    name = str(row.get("Saaja/maksja nimi", ""))
    account_raw = row.get("Saaja/maksja konto")

    account_info = {"iban": str(account_raw)} if not pd.isna(account_raw) else None

    if dc_indicator == "D":
        # Deebet -> Vastapool on Creditor
        tx["creditorName"] = name
        if account_info:
            tx["creditorAccount"] = account_info

    elif dc_indicator in ["C", "K"]:
        # Kreedit -> Vastapool on Debtor
        tx["debtorName"] = name
        if account_info:
            tx["debtorAccount"] = account_info


def _build_single_transaction(row: pd.Series, idx: int) -> Dict[str, Any]:
    """Koostab ühe PSD2 tehinguobjekti DataFrame'i reast."""
    amount = _parse_amount(row.get("Summa", 0))
    currency = row.get("Valuuta", "EUR")
    booking_date = str(row.get("Kuupäev"))

    tx = {
        "transactionId": _get_transaction_id(row, idx),
        "bookingDate": booking_date,
        "valueDate": booking_date,
        "transactionAmount": {
            "amount": f"{abs(amount):.2f}",
            "currency": currency
        },
        "remittanceInformationUnstructured": str(row.get("Selgitus", "")).replace("\\", " "),
    }

    # Lisa viitenumber, kui on
    viitenumber = row.get("Viitenumber")
    if not pd.isna(viitenumber):
        tx["remittanceInformationStructured"] = str(viitenumber)

    # Määra osapooled (muudab tx objekti viitena)
    _add_counterparty_details(tx, row)

    return tx


# --- PÕHIFUNKTSIOON ---

def parse_estonian_csv_to_psd2(csv_path: str | Path) -> Dict[str, Any]:
    """
    Peameetod: Loeb CSV ja tagastab PSD2 JSON struktuuri.
    Cognitive Complexity on nüüd madal, sest detailid on abifunktsioonides.
    """
    try:
        df = pd.read_csv(csv_path, sep=",")
    except FileNotFoundError:
        print(f"❌ Viga: Faili ei leitud: {csv_path}")
        return {}

    # Kasutame list comprehensionit tsükli asemel (kiirem ja puhtam)
    transactions = [_build_single_transaction(row, i) for i, row in df.iterrows()]

    # Leiame konto numbri esimesest reast
    account_iban = "UNKNOWN"
    if not df.empty and "Kliendi konto" in df.columns:
        account_iban = df.iloc[0]["Kliendi konto"]

    return {
        "account": {
            "iban": account_iban,
            "currency": "EUR"
        },
        "transactions": {
            "booked": transactions,
            "pending": []
        }
    }


# --- IO ja KÄIVITAMINE ---

def write_statement_json(data: Dict[str, Any], file_path: str | Path) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON salvestatud: {path}")


def run_pipeline() -> None:
    input_csv = "data/bank_test_2.csv"
    output_json = "data/output.json"

    print(f"🚀 Alustan: {input_csv} -> {output_json}")
    psd2_data = parse_estonian_csv_to_psd2(input_csv)

    if psd2_data:
        write_statement_json(psd2_data, output_json)


if __name__ == "__main__":
    run_pipeline()