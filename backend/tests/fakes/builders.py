"""Canonical test data builders for Berlin AIS pipeline tests.

Shared builders eliminate duplication across test files and ensure
consistent test data shapes.
"""

from __future__ import annotations


def make_accounts(
    resource_id: str = "acct-001",
    iban: str = "DE89370400440532013000",
    currency: str = "EUR",
    name: str = "Test Account",
) -> dict:
    """Return the smallest valid accounts.json payload."""
    return {
        "accounts": [
            {
                "resourceId": resource_id,
                "iban": iban,
                "currency": currency,
                "name": name,
            }
        ]
    }


def make_multi_accounts(*specs: tuple[str, str, str, str]) -> dict:
    """Return accounts.json with multiple accounts.

    Each spec is (resource_id, iban, currency, name).
    """
    return {
        "accounts": [
            {"resourceId": rid, "iban": iban, "currency": cur, "name": nm}
            for rid, iban, cur, nm in specs
        ]
    }


def make_tx(
    *,
    amount: str = "100.00",
    currency: str = "EUR",
    value_date: str = "2025-06-01",
    booking_date: str | None = "2025-06-01",
    debtor_name: str | None = "Alice",
    creditor_name: str | None = None,
    transaction_id: str | None = "TX001",
    remittance: str | None = "Test payment",
) -> dict:
    """Build a single Berlin AIS transaction dict."""
    t: dict = {
        "transactionAmount": {"amount": amount, "currency": currency},
        "valueDate": value_date,
    }
    if booking_date is not None:
        t["bookingDate"] = booking_date
    if debtor_name is not None:
        t["debtorName"] = debtor_name
        t["debtorAccount"] = {"iban": "NL91ABNA0417164300"}
    if creditor_name is not None:
        t["creditorName"] = creditor_name
        t["creditorAccount"] = {"iban": "GB29NWBK60161331926819"}
    if transaction_id is not None:
        t["transactionId"] = transaction_id
    if remittance is not None:
        t["remittanceInformationUnstructured"] = remittance
    return t


def make_report(
    iban: str = "DE89370400440532013000",
    booked: list | None = None,
    pending: list | None = None,
) -> dict:
    """Build a transactions.json payload."""
    return {
        "account": {"iban": iban},
        "transactions": {
            "booked": booked or [],
            "pending": pending or [],
        },
    }
