"""Edge-case tests at the pipeline input boundary.

Covers inputs that are plausible in real PSD2 feeds but historically untested:
- fully empty transaction list
- malformed JSON (must raise a clean error)
- UTF-8 BOM-prefixed files (common in Excel exports)
- Unicode counterparty names (Estonian/German/emoji)
- Cross-currency transactions on a single-currency account
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.fs._io import load_json
from application.pipeline import run_pipeline
from tests.fakes import (
    FakeDatasetPort,
    FakeOutputPort,
    FakeSpecPort,
    FakeValidationPort,
    FixedClock,
)
from tests.fakes.builders import make_accounts, make_report, make_tx


def _clock() -> FixedClock:
    return FixedClock(fixed_utc="2026-01-01T00:00:00Z", fixed_run_id="edge-run")


def _pipeline(booked: list[dict], pending: list[dict]) -> tuple[dict, FakeOutputPort]:
    dataset = FakeDatasetPort(
        accounts=make_accounts(),
        transaction_reports={
            "transactions.json": make_report(booked=booked, pending=pending),
        },
    )
    out = FakeOutputPort()
    summary = run_pipeline(
        dataset=dataset,
        out=out,
        spec=FakeSpecPort(),
        clock=_clock(),
        validator=FakeValidationPort(),
        dataset_id="edge-test",
        input_dir="<memory>",
    )
    return summary, out


class TestEmptyInput:
    def test_pipeline_handles_zero_transactions(self) -> None:
        summary, out = _pipeline(booked=[], pending=[])
        assert summary["counts"]["transactions_total"] == 0
        assert summary["counts"]["transactions_emitted_sv"] == 0
        assert summary["counts"]["transactions_dropped"] == 0
        assert out.sv is not None and out.sv["transactions"] == []


class TestMalformedJson:
    def test_load_json_raises_on_garbled_file(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_json(path)

    def test_load_json_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "missing.json")


class TestBomPrefixedJson:
    def test_load_json_rejects_utf8_bom(self, tmp_path: Path) -> None:
        """UTF-8 BOM (\\ufeff) at file start makes ``json.load`` fail loudly.

        We assert the current behaviour so that any future encoding change
        (e.g. switching to ``utf-8-sig``) shows up as a deliberate test update.
        """
        path = tmp_path / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf" + b'{"accounts": []}')
        with pytest.raises(json.JSONDecodeError):
            load_json(path)


class TestUnicodeCounterparty:
    def test_estonian_name_roundtrips(self) -> None:
        tx = make_tx(debtor_name="Café Tõnismäe OÜ", transaction_id="TXU-01")
        _, out = _pipeline(booked=[tx], pending=[])
        assert out.sv["transactions"][0]["counterparty"]["name"] == "Café Tõnismäe OÜ"

    def test_german_umlaut_name_roundtrips(self) -> None:
        tx = make_tx(debtor_name="Müller & Söhne GmbH", transaction_id="TXU-02")
        _, out = _pipeline(booked=[tx], pending=[])
        assert out.sv["transactions"][0]["counterparty"]["name"] == "Müller & Söhne GmbH"

    def test_emoji_name_roundtrips(self) -> None:
        tx = make_tx(debtor_name="Shop 🛒 A/S", transaction_id="TXU-03")
        _, out = _pipeline(booked=[tx], pending=[])
        assert out.sv["transactions"][0]["counterparty"]["name"] == "Shop 🛒 A/S"


class TestCrossCurrencyTransaction:
    def test_usd_transaction_on_eur_account_preserves_tx_currency(self) -> None:
        """Transaction currency may differ from account currency — SV must keep tx-level currency."""
        tx = make_tx(amount="250.00", transaction_id="TX-USD")
        tx["transactionAmount"]["currency"] = "USD"
        _, out = _pipeline(booked=[tx], pending=[])
        assert out.sv["transactions"][0]["amount"]["currency"] == "USD"
        assert out.sv["accounts"][0]["currency"] == "EUR"
