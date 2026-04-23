"""Unit tests for application.run_pipeline using in-memory fake ports.

These tests exercise the full 7-stage pipeline without touching the
filesystem — all I/O is handled by the fakes in tests/fakes/.
"""

from __future__ import annotations

import pytest

from application.pipeline import run_pipeline
from tests.fakes import FakeDatasetPort, FakeOutputPort, FakeSpecPort, FakeValidationPort, FixedClock
from tests.fakes.builders import make_accounts as _minimal_accounts, make_tx as _make_transaction, make_report as _transactions_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def clock() -> FixedClock:
    return FixedClock(fixed_utc="2026-01-01T00:00:00Z", fixed_run_id="fake-run-001")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineHappyPath:
    """Pipeline returns SUCCESS for a small, clean dataset with no errors."""

    @pytest.fixture()
    def result(self, clock: FixedClock) -> tuple[dict, FakeOutputPort]:
        booked = [
            _make_transaction(
                amount="250.00",
                value_date="2025-03-10",
                booking_date="2025-03-10",
                debtor_name="Alice Sender",
                transaction_id="TX001",
                remittance="Salary March",
            ),
            _make_transaction(
                amount="-45.99",
                value_date="2025-03-12",
                booking_date="2025-03-12",
                debtor_name=None,
                creditor_name="Supermarket GmbH",
                transaction_id="TX002",
                remittance="Groceries",
            ),
        ]
        pending = [
            _make_transaction(
                amount="1000.00",
                value_date="2025-03-20",
                booking_date=None,
                debtor_name="Bob Payer",
                transaction_id="TX003",
                remittance="Loan repayment",
            ),
        ]

        dataset = FakeDatasetPort(
            accounts=_minimal_accounts(),
            transaction_reports={
                "transactions.json": _transactions_report(
                    booked=booked, pending=pending,
                ),
            },
        )
        out = FakeOutputPort()
        spec = FakeSpecPort()

        summary = run_pipeline(
            dataset=dataset,
            out=out,
            spec=spec,
            clock=clock,
            validator=FakeValidationPort(),
            dataset_id="unit-test",
            input_dir="<memory>",
        )
        return summary, out

    def test_outcome_is_success(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["outcome"] == "SUCCESS"

    def test_run_id_matches_clock(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["run_id"] == "fake-run-001"

    def test_counts_accounts(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["counts"]["accounts_total"] == 1

    def test_counts_transactions_total(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["counts"]["transactions_total"] == 3

    def test_counts_emitted_equals_total(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["counts"]["transactions_emitted_sv"] == 3

    def test_counts_none_dropped(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["counts"]["transactions_dropped"] == 0

    def test_counts_ml_rows(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        # All 3 are BOOKED or PENDING → all included in ML
        assert summary["counts"]["ml_rows"] == 3

    def test_counts_llm_contexts(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        # 1 account → 1 LLM context
        assert summary["counts"]["llm_contexts"] == 1

    def test_no_issues(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["issues"] == []

    def test_no_dropped_details(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["dropped_details"] == []

    def test_severity_counts_all_zero(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        for sev in ("CRITICAL", "ERROR", "WARN", "INFO"):
            assert summary["by_severity"][sev] == 0, f"{sev} should be 0"
            assert summary["by_severity_issues"][sev] == 0, f"by_severity_issues[{sev}] should be 0"

    def test_output_port_received_sv(self, result: tuple[dict, FakeOutputPort]) -> None:
        _, out = result
        assert out.sv is not None
        assert len(out.sv["transactions"]) == 3

    def test_output_port_received_report(self, result: tuple[dict, FakeOutputPort]) -> None:
        _, out = result
        assert out.report is not None
        assert out.report["outcome"]["status"] == "SUCCESS"

    def test_output_port_received_ml(self, result: tuple[dict, FakeOutputPort]) -> None:
        _, out = result
        assert out.ml is not None
        assert len(out.ml) == 3

    def test_output_port_received_llm(self, result: tuple[dict, FakeOutputPort]) -> None:
        _, out = result
        assert out.llm is not None


class TestPipelineWithDroppedTransaction:
    """Pipeline handles a transaction that gets dropped (missing valueDate)."""

    @pytest.fixture()
    def result(self, clock: FixedClock) -> dict:
        good_tx = _make_transaction(
            amount="50.00",
            value_date="2025-06-01",
            booking_date="2025-06-01",
            debtor_name="Good Payer",
            transaction_id="TX-GOOD",
        )
        # Bad transaction: no valueDate, no bookingDate → mapping drop
        bad_tx: dict = {
            "transactionAmount": {"amount": "10.00", "currency": "EUR"},
            "transactionId": "TX-BAD",
        }

        dataset = FakeDatasetPort(
            accounts=_minimal_accounts(),
            transaction_reports={
                "transactions.json": _transactions_report(booked=[good_tx, bad_tx]),
            },
        )
        out = FakeOutputPort()
        spec = FakeSpecPort()

        return run_pipeline(
            dataset=dataset,
            out=out,
            spec=spec,
            clock=clock,
            validator=FakeValidationPort(),
            dataset_id="unit-drop-test",
            input_dir="<memory>",
        )

    def test_outcome_is_fail(self, result: dict) -> None:
        # 1 mapping drop out of 2 total = 50%, which exceeds the 5% fail-gate
        # threshold.  Mapping drops count as error drops in determine_outcome.
        assert result["outcome"] == "FAIL"

    def test_one_transaction_dropped(self, result: dict) -> None:
        assert result["counts"]["transactions_dropped"] == 1

    def test_one_transaction_emitted(self, result: dict) -> None:
        assert result["counts"]["transactions_emitted_sv"] == 1

    def test_total_transactions(self, result: dict) -> None:
        assert result["counts"]["transactions_total"] == 2

    def test_dropped_details_present(self, result: dict) -> None:
        assert len(result["dropped_details"]) == 1
        detail = result["dropped_details"][0]
        assert "valueDate" in detail.get("drop_reason", "")


# ---------------------------------------------------------------------------
# Real-schema validation: guards against fake-vs-real parity drift
# ---------------------------------------------------------------------------

class TestPipelineWithRealSchemas:
    """Run the pipeline with real JSON Schemas and a real validator.

    This catches spec-compliance bugs (e.g. severity enum mismatches) that
    FakeSpecPort + FakeValidationPort silently ignore.
    """

    @pytest.fixture()
    def result(self, clock: FixedClock) -> tuple[dict, FakeOutputPort]:
        from pathlib import Path
        from adapters.fs.spec_fs import FsSpecAdapter
        from adapters.validation.jsonschema_adapter import JsonSchemaValidationAdapter

        spec_dir = Path(__file__).resolve().parents[3] / "spec"
        spec = FsSpecAdapter(spec_dir)
        validator = JsonSchemaValidationAdapter()

        booked = [
            _make_transaction(
                amount="250.00",
                value_date="2025-03-10",
                booking_date="2025-03-10",
                debtor_name="Alice Sender",
                transaction_id="TX001",
                remittance="Salary March",
            ),
            _make_transaction(
                amount="-45.99",
                value_date="2025-03-12",
                booking_date="2025-03-12",
                debtor_name=None,
                creditor_name="Supermarket GmbH",
                transaction_id="TX002",
                remittance="Groceries",
            ),
        ]

        dataset = FakeDatasetPort(
            accounts=_minimal_accounts(),
            transaction_reports={
                "transactions.json": _transactions_report(booked=booked),
            },
        )
        out = FakeOutputPort()

        summary = run_pipeline(
            dataset=dataset,
            out=out,
            spec=spec,
            clock=clock,
            validator=validator,
            dataset_id="real-schema-test",
            input_dir="<memory>",
        )
        return summary, out

    def test_outcome_is_success(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        assert summary["outcome"] == "SUCCESS"

    def test_no_schema_errors(self, result: tuple[dict, FakeOutputPort]) -> None:
        summary, _ = result
        schema_issues = [i for i in summary["issues"] if "VALIDATION" in i.get("code", "")]
        assert schema_issues == [], f"Schema validation errors: {schema_issues}"

    def test_sv_output_present(self, result: tuple[dict, FakeOutputPort]) -> None:
        _, out = result
        assert out.sv is not None
        assert len(out.sv["transactions"]) == 2
