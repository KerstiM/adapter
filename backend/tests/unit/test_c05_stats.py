"""C-05 statistikaprojektsiooni funktsionaalsed testid.

Testivad project_stats() sisemist loogikat: agregeerimist, sorteerimist,
perioodi piire, tühja sisendit.  Laiendatavuse tõendid (callable_on_pipeline,
existing_projections_unchanged, no_io_imports) on test_scalability.py-s.
"""

from __future__ import annotations

from domain.projections.c05_sv_to_stats import project_stats
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
        dataset_id="c05-test", input_dir="<memory>",
    )
    return out


# ---------------------------------------------------------------------------
# Testid
# ---------------------------------------------------------------------------

class TestC05Stats:
    """C-05 project_stats() funktsionaalsed testid."""

    def test_produces_stats_for_single_account(self) -> None:
        """C-05 tagastab ühe konto statistika minimaalselt sisendilt."""
        out = _run(booked=[_tx(amount="50.00"), _tx(amount="-30.00", transaction_id="TX002")])
        stats = project_stats(out.sv)

        assert len(stats) == 1
        s = stats[0]
        assert s["account_id"] == "acct-001"
        assert s["currency"] == "EUR"
        assert s["transaction_count"]["total"] == 2

    def test_produces_stats_for_multiple_accounts(self) -> None:
        """C-05 tagastab statistika iga konto kohta eraldi."""
        accounts = _multi_accounts(
            ("acct-001", "DE89370400440532013000", "EUR", "Account A"),
            ("acct-002", "GB29NWBK60161331926819", "GBP", "Account B"),
        )
        reports = {
            "tx_acct1.json": _report(
                iban="DE89370400440532013000",
                booked=[_tx(amount="100.00", transaction_id="TX-A1")],
            ),
            "tx_acct2.json": _report(
                iban="GB29NWBK60161331926819",
                booked=[_tx(amount="200.00", transaction_id="TX-B1")],
            ),
        }
        out = _run(accounts=accounts, transaction_reports=reports)
        stats = project_stats(out.sv)

        assert len(stats) == 2
        account_ids = {s["account_id"] for s in stats}
        assert "acct-001" in account_ids
        assert "acct-002" in account_ids

    def test_inflow_outflow_correct(self) -> None:
        """C-05 agregeerib sissevoolu ja väljavoolu korrektselt."""
        booked = [
            _tx(amount="100.00", transaction_id="TX-IN1", debtor_name="Payer A", creditor_name=None),
            _tx(amount="250.00", transaction_id="TX-IN2", debtor_name="Payer B", creditor_name=None),
            _tx(amount="80.00", transaction_id="TX-OUT1", creditor_name="Vendor X", debtor_name=None),
            _tx(amount="20.00", transaction_id="TX-OUT2", creditor_name="Vendor Y", debtor_name=None),
        ]
        out = _run(booked=booked)
        stats = project_stats(out.sv)

        s = stats[0]
        assert s["inflow"]["count"] == 2
        assert s["inflow"]["total"] == "350"
        assert s["outflow"]["count"] == 2
        assert s["outflow"]["total"] == "-100"

    def test_top_counterparties_sorted_by_total(self) -> None:
        """C-05 sorteerib vastaspooled absoluutsumma järgi kahanevalt."""
        booked = [
            _tx(amount="-500.00", transaction_id="TX1", creditor_name="Big Corp", debtor_name=None),
            _tx(amount="-100.00", transaction_id="TX2", creditor_name="Small LLC", debtor_name=None),
            _tx(amount="-300.00", transaction_id="TX3", creditor_name="Big Corp", debtor_name=None),
        ]
        out = _run(booked=booked)
        stats = project_stats(out.sv)

        cps = stats[0]["top_counterparties"]
        assert len(cps) == 2
        assert cps[0]["name"] == "Big Corp"
        assert cps[1]["name"] == "Small LLC"

    def test_handles_empty_transactions(self) -> None:
        """C-05 käsitleb tühja tehinguloendit korrektselt."""
        out = _run(booked=[], pending=[])
        stats = project_stats(out.sv)

        assert len(stats) == 1
        s = stats[0]
        assert s["transaction_count"]["total"] == 0
        assert s["inflow"]["count"] == 0
        assert s["outflow"]["count"] == 0
        assert s["period"] == {}
        assert s["top_counterparties"] == []

    def test_period_boundaries_correct(self) -> None:
        """C-05 arvutab perioodi piirid min/max kuupäevadest."""
        booked = [
            _tx(amount="10.00", value_date="2025-03-15", booking_date="2025-03-15", transaction_id="TX1"),
            _tx(amount="20.00", value_date="2025-01-10", booking_date="2025-01-10", transaction_id="TX2"),
            _tx(amount="30.00", value_date="2025-06-20", booking_date="2025-06-20", transaction_id="TX3"),
        ]
        out = _run(booked=booked)
        stats = project_stats(out.sv)

        period = stats[0]["period"]
        assert period["from"] == "2025-01-10"
        assert period["to"] == "2025-06-20"
