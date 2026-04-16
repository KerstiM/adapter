"""C-06 kuubilansi projektsiooni funktsionaalsed testid.

Testivad project_monthly_balance() sisemist loogikat: aegrea kuju,
kronoloogilist sorteerimist, kumulatiivset saldot, kontode isolatsiooni,
tühja sisendit.  Laiendatavuse tõendid (callable_on_pipeline,
existing_projections_unchanged, no_io_imports) on test_scalability.py-s.
"""

from __future__ import annotations

from domain.projections.c06_sv_to_monthly_balance import project_monthly_balance
from tests.fakes import FakeDatasetPort, FakeOutputPort, FakeSpecPort, FakeValidationPort, FixedClock
from tests.fakes.builders import make_accounts as _accounts, make_multi_accounts as _multi_accounts, make_tx as _tx, make_report as _report
from application.pipeline import run_pipeline


def _run(
    *,
    accounts: dict | None = None,
    booked: list | None = None,
    pending: list | None = None,
    transaction_reports: dict | None = None,
) -> FakeOutputPort:
    if transaction_reports is None:
        transaction_reports = {
            "transactions.json": _report(booked=booked or [], pending=pending or []),
        }
    dataset = FakeDatasetPort(
        accounts=accounts or _accounts(),
        transaction_reports=transaction_reports,
    )
    out = FakeOutputPort()
    spec = FakeSpecPort()
    clock = FixedClock()
    run_pipeline(
        dataset=dataset, out=out, spec=spec, clock=clock, validator=FakeValidationPort(),
        dataset_id="c06-test", input_dir="<memory>",
    )
    return out


# ---------------------------------------------------------------------------
# Testid
# ---------------------------------------------------------------------------

class TestC06MonthlyBalance:
    """C-06 project_monthly_balance() funktsionaalsed testid."""

    def test_output_shape_is_time_series(self) -> None:
        """C-06 väljundi kuju on ajaseeria bucket'idega (month, net, running_balance)."""
        booked = [
            _tx(amount="200.00", transaction_id="TX1", value_date="2025-01-10", booking_date="2025-01-10"),
            _tx(amount="-80.00", transaction_id="TX2", creditor_name="Vendor", debtor_name=None, value_date="2025-02-05", booking_date="2025-02-05"),
            _tx(amount="50.00", transaction_id="TX3", value_date="2025-03-01", booking_date="2025-03-01"),
        ]
        out = _run(booked=booked)

        timelines = project_monthly_balance(out.sv)
        assert isinstance(timelines, list) and len(timelines) == 1

        entry = timelines[0]
        assert set(entry.keys()) == {"account_id", "iban", "currency", "timeline"}
        assert isinstance(entry["timeline"], list)
        assert len(entry["timeline"]) == 3

        bucket = entry["timeline"][0]
        expected_bucket_keys = {
            "month",
            "inflow_count", "inflow_total",
            "outflow_count", "outflow_total",
            "net", "running_balance",
        }
        assert set(bucket.keys()) == expected_bucket_keys

    def test_monthly_buckets_sorted_chronologically(self) -> None:
        """C-06 bucket'id tulevad kronoloogilises järjekorras."""
        booked = [
            _tx(amount="10.00", transaction_id="TX-JUN", value_date="2025-06-15", booking_date="2025-06-15"),
            _tx(amount="20.00", transaction_id="TX-MAR", value_date="2025-03-20", booking_date="2025-03-20"),
            _tx(amount="30.00", transaction_id="TX-SEP", value_date="2025-09-05", booking_date="2025-09-05"),
            _tx(amount="40.00", transaction_id="TX-JAN", value_date="2025-01-10", booking_date="2025-01-10"),
        ]
        out = _run(booked=booked)

        timelines = project_monthly_balance(out.sv)
        months = [b["month"] for b in timelines[0]["timeline"]]

        assert months == ["2025-01", "2025-03", "2025-06", "2025-09"]

    def test_running_balance_accumulates(self) -> None:
        """Jooksev saldo on eelmiste netide kumulatiivne summa."""
        booked = [
            _tx(amount="100.00", transaction_id="TX-JAN1",
                value_date="2025-01-10", booking_date="2025-01-10"),
            _tx(amount="-30.00", transaction_id="TX-FEB1",
                creditor_name="Vendor", debtor_name=None,
                value_date="2025-02-05", booking_date="2025-02-05"),
            _tx(amount="50.00", transaction_id="TX-MAR1",
                value_date="2025-03-02", booking_date="2025-03-02"),
        ]
        out = _run(booked=booked)

        timeline = project_monthly_balance(out.sv)[0]["timeline"]
        assert len(timeline) == 3

        assert timeline[0]["month"] == "2025-01"
        assert timeline[0]["net"] == "100"
        assert timeline[0]["running_balance"] == "100"

        assert timeline[1]["month"] == "2025-02"
        assert timeline[1]["net"] == "-30"
        assert timeline[1]["running_balance"] == "70"

        assert timeline[2]["month"] == "2025-03"
        assert timeline[2]["net"] == "50"
        assert timeline[2]["running_balance"] == "120"

    def test_multi_account_isolation(self) -> None:
        """Iga konto saab oma iseseisva aegrea; kontode vahel ei toimu lekkimist."""
        accounts = _multi_accounts(
            ("acct-001", "DE89370400440532013000", "EUR", "Account A"),
            ("acct-002", "GB29NWBK60161331926819", "GBP", "Account B"),
        )
        reports = {
            "tx_acct1.json": _report(
                iban="DE89370400440532013000",
                booked=[
                    _tx(amount="100.00", transaction_id="A-JAN",
                        value_date="2025-01-10", booking_date="2025-01-10"),
                    _tx(amount="200.00", transaction_id="A-FEB",
                        value_date="2025-02-10", booking_date="2025-02-10"),
                ],
            ),
            "tx_acct2.json": _report(
                iban="GB29NWBK60161331926819",
                booked=[
                    _tx(amount="500.00", transaction_id="B-MAR",
                        value_date="2025-03-15", booking_date="2025-03-15"),
                ],
            ),
        }
        out = _run(accounts=accounts, transaction_reports=reports)

        timelines = project_monthly_balance(out.sv)
        by_id = {t["account_id"]: t for t in timelines}

        assert set(by_id.keys()) == {"acct-001", "acct-002"}

        months_a = [b["month"] for b in by_id["acct-001"]["timeline"]]
        months_b = [b["month"] for b in by_id["acct-002"]["timeline"]]
        assert months_a == ["2025-01", "2025-02"]
        assert months_b == ["2025-03"]

        assert by_id["acct-001"]["timeline"][-1]["running_balance"] == "300"
        assert by_id["acct-002"]["timeline"][-1]["running_balance"] == "500"

    def test_handles_empty_transactions(self) -> None:
        """C-06 tühja tehinguloendiga annab tühja aegrea."""
        out = _run(booked=[], pending=[])

        timelines = project_monthly_balance(out.sv)
        assert len(timelines) == 1
        assert timelines[0]["account_id"] == "acct-001"
        assert timelines[0]["timeline"] == []
