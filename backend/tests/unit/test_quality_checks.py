"""Direct unit tests for domain.rules.quality_checks (QC-1)."""

from __future__ import annotations

from domain.rules.quality_checks import check_quality
from tests.fakes import load_spec_rulesets

_QC = load_spec_rulesets()["QC"]


def _tx(name=None, iban=None) -> dict:
    return {
        "counterparty": {"name": name, "iban": iban},
        "flags": [],
    }


class TestQC01CounterpartyMissing:
    def test_both_missing_emits_info_flag(self) -> None:
        tx = _tx(name=None, iban=None)
        check_quality([tx], _QC)
        assert any(
            f["id"] == "QC-1_COUNTERPARTY_MISSING" and f["severity"] == "INFO"
            for f in tx["flags"]
        )

    def test_name_present_does_not_flag(self) -> None:
        tx = _tx(name="Sender AS", iban=None)
        check_quality([tx], _QC)
        assert all(f["id"] != "QC-1_COUNTERPARTY_MISSING" for f in tx["flags"])

    def test_iban_present_does_not_flag(self) -> None:
        tx = _tx(name=None, iban="EE111")
        check_quality([tx], _QC)
        assert all(f["id"] != "QC-1_COUNTERPARTY_MISSING" for f in tx["flags"])

    def test_both_present_does_not_flag(self) -> None:
        tx = _tx(name="Sender", iban="EE111")
        check_quality([tx], _QC)
        assert tx["flags"] == []

    def test_empty_list_is_noop(self) -> None:
        check_quality([], _QC)  # must not raise

    def test_preserves_existing_flags(self) -> None:
        tx = _tx(name=None, iban=None)
        tx["flags"].append({"id": "X-PRE", "severity": "WARN", "message": "pre"})
        check_quality([tx], _QC)
        ids = [f["id"] for f in tx["flags"]]
        assert "X-PRE" in ids and "QC-1_COUNTERPARTY_MISSING" in ids
