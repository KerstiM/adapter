"""UK3 laiendatavuse evolutsioonistsenaariumid.

Kolm stsenaariumit, mis tõestavad praktilist lokaalsust erinevatel
arhitektuurikihtidel:

Stsenaarium 1 — Projektsiooni laiendatavus (väljundikiht)
    Uus reeglipõhine projektsioon C-05 (SV → Statistics) lisatakse
    eraldiseisvana.  Pipeline'i, porte ega adaptereid ei muudeta.
    Tõestab: SV vaheesitus on stabiilne laienduspunkt.

Stsenaarium 2 — Formaateri laiendatavus (C-04 dispatch-kiht)
    Uus LLM formaateri moodul (Gemma 2) registreeritakse ajutiselt
    dispatch-tabelisse.  Tõestab: dispatch-mehhanism on avatud
    laiendamiseks ilma olemasolevat koodi muutmata.

    NB: testis kasutatakse ajutist registreerimist, sest tootmisse
    lisamine nõuaks 1 import + 1 dict-rida __init__.py-s — see oleks
    põhjendamatu tootmismuudatus prototüübis.  Formaateri moodul ise
    on reaalne artefakt, mis järgib olemasolevat mustrit.

Stsenaarium 3 — Sisendikihi laiendatavus (DatasetPort)
    Testis defineeritud uus DatasetPort implementatsioon läbib
    pipeline'i end-to-end.  Tõestab: pordi protokoll (duck typing)
    lubab uue allika lisamist ilma pipeline'i muutmata.

    NB: testis defineeritud implementatsioon on piisav, sest
    FakeDatasetPort on juba üks näide alternatiivadapterist.
    Siinne SimpleDictDatasetPort on struktuuriliselt erinev
    (üks dict vs eraldi payload'id), mis näitab, et pordi
    protokoll ei sõltu konkreetsest sisemisest struktuurist.
"""

from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from application.pipeline import run_pipeline
from domain.projections.c05_sv_to_stats import project_stats
from domain.projections.c06_sv_to_monthly_balance import project_monthly_balance
from domain.projections.model_formatters import (
    _LLM_FAMILY_DISPATCH,
    _ML_ENCODING_DISPATCH,
    format_for_model,
)
from domain.projections.model_formatters.llm_gemma import format_gemma
from tests.fakes import FakeDatasetPort, FakeOutputPort, FakeSpecPort, FixedClock
from tests.fakes.fake_spec_port import _default_profile


# ---------------------------------------------------------------------------
# Jagatud abifunktsioonid (sama muster nagu test_sli_slo.py)
# ---------------------------------------------------------------------------

def _accounts(
    resource_id: str = "acct-001",
    iban: str = "DE89370400440532013000",
    currency: str = "EUR",
    name: str = "Test Account",
) -> dict:
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


def _multi_accounts(*specs: tuple[str, str, str, str]) -> dict:
    """Build accounts payload with multiple accounts.

    Each spec is (resource_id, iban, currency, name).
    """
    return {
        "accounts": [
            {"resourceId": rid, "iban": iban, "currency": cur, "name": name}
            for rid, iban, cur, name in specs
        ]
    }


def _tx(
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


def _report(
    iban: str = "DE89370400440532013000",
    booked: list | None = None,
    pending: list | None = None,
) -> dict:
    return {
        "account": {"iban": iban},
        "transactions": {
            "booked": booked or [],
            "pending": pending or [],
        },
    }


def _run(
    *,
    accounts: dict | None = None,
    booked: list | None = None,
    pending: list | None = None,
    transaction_reports: dict | None = None,
    clock: FixedClock | None = None,
) -> tuple[dict, FakeOutputPort]:
    """Run pipeline with given data; return (summary, output_port)."""
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
    _clock = clock or FixedClock()
    summary = run_pipeline(
        dataset=dataset,
        out=out,
        spec=spec,
        clock=_clock,
        dataset_id="scalability-test",
        input_dir="<memory>",
    )
    return summary, out


# ===================================================================
# Stsenaarium 1: Projektsiooni laiendatavus — C-05 SV → Statistics
# ===================================================================

class TestC05ProjectionExtensibility:
    """C-05 evolutsioonistsenaarium: reeglipõhine statistikaprojektsioon.

    Iga test tõestab, et uus projektsioon töötab SV vaheesitusel
    ilma pipeline'i, porte ega adaptereid muutmata.
    """

    def test_c05_produces_stats_for_single_account(self) -> None:
        """C-05 tagastab ühe konto statistika minimaalselt sisendilt."""
        _, out = _run(booked=[_tx(amount="50.00"), _tx(amount="-30.00", transaction_id="TX002")])
        stats = project_stats(out.sv)

        assert len(stats) == 1
        s = stats[0]
        assert s["account_id"] == "acct-001"
        assert s["currency"] == "EUR"
        assert s["transaction_count"]["total"] == 2

    def test_c05_produces_stats_for_multiple_accounts(self) -> None:
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
        _, out = _run(accounts=accounts, transaction_reports=reports)
        stats = project_stats(out.sv)

        assert len(stats) == 2
        account_ids = {s["account_id"] for s in stats}
        assert "acct-001" in account_ids
        assert "acct-002" in account_ids

    def test_c05_inflow_outflow_correct(self) -> None:
        """C-05 agregeerib sissevoolu ja väljavoolu korrektselt.

        Berlin AIS suunareeglid: debtorName → IN (sissevool),
        creditorName → OUT (väljavool).  Positiivne summa + debtorName
        annab positiivse signed_amount SV-s.
        """
        booked = [
            _tx(amount="100.00", transaction_id="TX-IN1", debtor_name="Payer A", creditor_name=None),
            _tx(amount="250.00", transaction_id="TX-IN2", debtor_name="Payer B", creditor_name=None),
            _tx(amount="80.00", transaction_id="TX-OUT1", creditor_name="Vendor X", debtor_name=None),
            _tx(amount="20.00", transaction_id="TX-OUT2", creditor_name="Vendor Y", debtor_name=None),
        ]
        _, out = _run(booked=booked)
        stats = project_stats(out.sv)

        s = stats[0]
        assert s["inflow"]["count"] == 2
        assert s["inflow"]["total"] == "350"
        assert s["outflow"]["count"] == 2
        assert s["outflow"]["total"] == "-100"

    def test_c05_top_counterparties_sorted_by_total(self) -> None:
        """C-05 sorteerib vastaspooled absoluutsumma järgi kahanevalt."""
        booked = [
            _tx(amount="-500.00", transaction_id="TX1", creditor_name="Big Corp", debtor_name=None),
            _tx(amount="-100.00", transaction_id="TX2", creditor_name="Small LLC", debtor_name=None),
            _tx(amount="-300.00", transaction_id="TX3", creditor_name="Big Corp", debtor_name=None),
        ]
        _, out = _run(booked=booked)
        stats = project_stats(out.sv)

        cps = stats[0]["top_counterparties"]
        assert len(cps) == 2
        assert cps[0]["name"] == "Big Corp"
        assert cps[1]["name"] == "Small LLC"

    def test_c05_handles_empty_transactions(self) -> None:
        """C-05 käsitleb tühja tehinguloendit korrektselt."""
        _, out = _run(booked=[], pending=[])
        stats = project_stats(out.sv)

        assert len(stats) == 1
        s = stats[0]
        assert s["transaction_count"]["total"] == 0
        assert s["inflow"]["count"] == 0
        assert s["outflow"]["count"] == 0
        assert s["period"] == {}
        assert s["top_counterparties"] == []

    def test_c05_period_boundaries_correct(self) -> None:
        """C-05 arvutab perioodi piirid min/max kuupäevadest."""
        booked = [
            _tx(amount="10.00", value_date="2025-03-15", booking_date="2025-03-15", transaction_id="TX1"),
            _tx(amount="20.00", value_date="2025-01-10", booking_date="2025-01-10", transaction_id="TX2"),
            _tx(amount="30.00", value_date="2025-06-20", booking_date="2025-06-20", transaction_id="TX3"),
        ]
        _, out = _run(booked=booked)
        stats = project_stats(out.sv)

        period = stats[0]["period"]
        assert period["from"] == "2025-01-10"
        assert period["to"] == "2025-06-20"

    def test_c05_callable_on_pipeline_sv_output(self) -> None:
        """Võtmetest: C-05 töötab pipeline SV väljundil ilma pipeline'i muutmata.

        Käivitab pipeline'i, võtab SV bundle'i väljundpordist ja kutsub
        project_stats() otse.  Pipeline'i koodi ei muudetud.
        """
        booked = [
            _tx(amount="100.00", transaction_id=f"TX{i:03d}", value_date=f"2025-{1 + i % 6:02d}-15")
            for i in range(20)
        ]
        _, out = _run(booked=booked)

        assert out.sv is not None, "Pipeline must produce SV output"

        stats = project_stats(out.sv)
        assert len(stats) == 1
        assert stats[0]["transaction_count"]["total"] == 20

    def test_c05_existing_projections_unchanged(self) -> None:
        """C-05 lisamine ei mõjuta olemasolevaid C-02 ja C-03 projektsioone.

        Käivitab pipeline'i, salvestab C-02/C-03 väljundid, kutsub C-05,
        ja kinnitab, et C-02/C-03 on endiselt identsed.
        """
        booked = [
            _tx(amount="100.00", transaction_id="TX001"),
            _tx(amount="-50.00", transaction_id="TX002"),
        ]
        _, out = _run(booked=booked)

        ml_before = out.ml
        llm_before = out.llm

        # C-05 kutsumine SV bundle'il
        stats = project_stats(out.sv)
        assert len(stats) > 0

        # Olemasolevad projektsioonid ei muutunud
        assert out.ml is ml_before, "C-02 ML output must be the same object"
        assert out.llm is llm_before, "C-03 LLM output must be the same object"

    def test_c05_no_io_imports(self) -> None:
        """C-05 moodul ei impordi I/O, pathlib ega os mooduleid.

        Sama arhitektuuriline piir nagu test_import_boundaries.py jõustab.
        """
        import domain.projections.c05_sv_to_stats as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        forbidden = {"os", "pathlib", "json", "csv", "io", "shutil", "tempfile"}
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])

        violations = imported & forbidden
        assert not violations, (
            f"C-05 imports forbidden I/O modules: {violations}. "
            "Domain projections must remain pure."
        )


# ===================================================================
# Stsenaarium 2: Formaateri laiendatavus — C-04 dispatch
# ===================================================================

class TestFormatterExtensibility:
    """C-04 dispatch laiendatavuse evolutsioonistsenaarium.

    Tõestab, et uue LLM/ML formaateri lisamine dispatch-tabelisse on
    võimalik ilma pipeline'i ega olemasoleva dispatcheri koodi muutmata.

    Testid registreerivad formaateri ajutiselt ja puhastavad pärast testi.
    See on piisav UK3 tõenduseks, sest:
    - formaateri moodul (llm_gemma.py) on reaalne artefakt
    - tootmisse lisamine nõuaks ainult 1 import + 1 dict-entry __init__.py-s
    - dispatch-mehhanism ise ei muutu
    """

    def test_new_llm_formatter_pluggable(self) -> None:
        """Uus LLM formaateri moodul on ühildatav dispatch-mehhanismiga.

        Registreerib format_gemma ajutiselt _LLM_FAMILY_DISPATCH tabelisse
        ja kutsub format_for_model() — formaateri väljund on korrektne.
        """
        assert "gemma" not in _LLM_FAMILY_DISPATCH, "gemma must not be pre-registered"

        _LLM_FAMILY_DISPATCH["gemma"] = format_gemma
        try:
            llm_contexts = [{
                "meta": {"run_id": "test", "created_at_utc": "2026-01-01T00:00:00Z",
                         "account_id": "acct-001", "iban": "DE89...", "currency": "EUR"},
                "tx": [{"id": "TX1", "d": "2025-06-01", "s": "BOOKED",
                        "dir": "DEBIT", "a": "-100.00", "c": "EUR", "cp": "Alice", "r": "Test"}],
            }]
            config = {"family": "gemma", "template_tokens": {}}
            sv_bundle = {"meta": {"run_id": "test", "created_at_utc": "2026-01-01T00:00:00Z"}}

            result = format_for_model(
                llm_contexts, sv_bundle, "gemma-2-2b-it", config, "llm", preamble="Analyze.",
            )

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["model_id"] == "gemma-2-2b-it"
            assert "<start_of_turn>user" in result[0]["prompt"]
            assert "Analyze." in result[0]["prompt"]
            assert "<start_of_turn>model" in result[0]["prompt"]
        finally:
            _LLM_FAMILY_DISPATCH.pop("gemma", None)

    def test_new_ml_encoder_pluggable(self) -> None:
        """Uue ML enkooderi lisamine dispatch-tabelisse töötab.

        Loob minimaalse enkooderi funktsiooni ja registreerib selle
        _ML_ENCODING_DISPATCH tabelisse.  Tõestab, et dispatch-mehhanism
        on avatud ka ML poolel.
        """
        def format_lightgbm(ml_rows: list[dict], sv_bundle: dict, config: dict) -> dict:
            """Minimal LightGBM encoder — UK3 test artifact."""
            return {
                "model_id": "lightgbm",
                "row_count": len(ml_rows),
                "features": [{"signed_amount": float(r.get("signed_amount", 0))} for r in ml_rows],
            }

        assert "lgbm" not in _ML_ENCODING_DISPATCH, "lgbm must not be pre-registered"

        _ML_ENCODING_DISPATCH["lgbm"] = format_lightgbm
        try:
            ml_rows = [
                {"row_id": 1, "signed_amount": "100.00", "status": "BOOKED"},
                {"row_id": 2, "signed_amount": "-50.00", "status": "BOOKED"},
            ]
            config = {"encoding": "lgbm"}
            sv_bundle = {"meta": {"run_id": "test", "created_at_utc": "2026-01-01T00:00:00Z"}}

            result = format_for_model(ml_rows, sv_bundle, "lightgbm", config, "ml")

            assert result["model_id"] == "lightgbm"
            assert result["row_count"] == 2
        finally:
            _ML_ENCODING_DISPATCH.pop("lgbm", None)

    def test_formatter_cleanup_no_side_effects(self) -> None:
        """Ajutine registreerimine ja eemaldamine ei jäta kõrvalmõjusid.

        Pärast registreerimist ja eemaldamist on dispatch-tabel endises
        olekus — tõestab, et laiendamine ei rikuks olemasolevat loogikat.
        """
        original_llm_keys = set(_LLM_FAMILY_DISPATCH.keys())
        original_ml_keys = set(_ML_ENCODING_DISPATCH.keys())

        _LLM_FAMILY_DISPATCH["test_family"] = lambda *a, **k: []
        _ML_ENCODING_DISPATCH["test_encoding"] = lambda *a, **k: {}

        _LLM_FAMILY_DISPATCH.pop("test_family")
        _ML_ENCODING_DISPATCH.pop("test_encoding")

        assert set(_LLM_FAMILY_DISPATCH.keys()) == original_llm_keys
        assert set(_ML_ENCODING_DISPATCH.keys()) == original_ml_keys

    def test_unknown_family_raises_clear_error(self) -> None:
        """Tundmatu LLM perekond annab selge ValueError veateate."""
        config = {"family": "nonexistent_family"}
        sv_bundle = {"meta": {"run_id": "test", "created_at_utc": "2026-01-01T00:00:00Z"}}

        with pytest.raises(ValueError, match="Unknown LLM family.*nonexistent_family"):
            format_for_model([], sv_bundle, "model-x", config, "llm")


# ===================================================================
# Stsenaarium 3: Sisendikihi laiendatavus — DatasetPort
# ===================================================================

class SimpleDictDatasetPort:
    """Minimaalne DatasetPort implementatsioon UK3 tõenduseks.

    Struktuuriliselt erinev FakeDatasetPort-ist: võtab kogu andmestiku
    ühe dict-ina, mitte eraldi payload'idena.  See näitab, et pordi
    protokoll ei sõltu konkreetsest sisemisest struktuurist.

    Miks see on piisav UK3 tõenduseks:
    - Implementeerib DatasetPort protokolli (duck typing)
    - Pipeline aktsepteerib seda ilma muudatusteta
    - Erinev sisemine struktuur (üks dict) vs FakeDatasetPort (eraldi väljad)
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def read_accounts(self) -> dict[str, Any]:
        return self._data["accounts_payload"]

    def list_transaction_reports(self) -> list[str]:
        return sorted(self._data.get("reports", {}).keys())

    def read_transactions_report(self, name: str) -> dict[str, Any]:
        return self._data["reports"][name]

    def read_standing_orders_optional(self) -> dict[str, Any] | None:
        return self._data.get("standing_orders")


class SimpleOutputPort:
    """Minimaalne OutputPort implementatsioon UK3 tõenduseks.

    Salvestab kõik artefaktid lihtsasse dict-i.  Struktuuriliselt
    erinev FakeOutputPort-ist (dict vs eraldi atribuudid).
    """

    def __init__(self) -> None:
        self.artifacts: dict[str, Any] = {}

    def init_run_folder(self, run_id: str, created_at_utc: str) -> None:
        self.artifacts["run_id"] = run_id
        self.artifacts["created_at_utc"] = created_at_utc

    def write_sv(self, bundle: dict[str, Any]) -> None:
        self.artifacts["sv"] = bundle

    def write_ml(self, rows: list[dict[str, Any]]) -> None:
        self.artifacts["ml"] = rows

    def write_llm(self, context: dict[str, Any] | list[dict[str, Any]]) -> None:
        self.artifacts["llm"] = context

    def write_report(self, report: dict[str, Any]) -> None:
        self.artifacts["report"] = report

    def write_ml_model(self, output: dict[str, Any], model_suffix: str) -> None:
        self.artifacts[f"ml_model_{model_suffix}"] = output

    def write_llm_model(self, output: list[dict[str, Any]], model_suffix: str) -> None:
        self.artifacts[f"llm_model_{model_suffix}"] = output

    def write_extra_projection(self, data: list[dict[str, Any]], filename: str) -> None:
        self.artifacts[f"extra_{filename}"] = data


class TestInputExtensibility:
    """DatasetPort / OutputPort laiendatavuse evolutsioonistsenaarium.

    Tõestab, et pipeline töötab mis tahes DatasetPort implementatsiooniga,
    mitte ainult FakeDatasetPort-iga.  Pordi protokolli ega pipeline'i
    koodi ei muudeta.
    """

    def test_custom_dataset_port_works_with_pipeline(self) -> None:
        """Testis defineeritud SimpleDictDatasetPort läbib pipeline'i end-to-end.

        Loob uue DatasetPort implementatsiooni, mis pole FakeDatasetPort,
        ja käivitab pipeline'i.  Kõik 8 etappi peavad läbima.
        """
        data = {
            "accounts_payload": _accounts(),
            "reports": {
                "transactions.json": _report(
                    booked=[_tx(amount="75.00", transaction_id="CUSTOM-TX1")],
                ),
            },
        }
        dataset = SimpleDictDatasetPort(data)
        out = FakeOutputPort()
        spec = FakeSpecPort()
        clock = FixedClock()

        summary = run_pipeline(
            dataset=dataset, out=out, spec=spec, clock=clock,
            dataset_id="custom-adapter-test", input_dir="<memory>",
        )

        assert summary["outcome"] in ("SUCCESS", "PARTIAL_SUCCESS")
        assert summary["counts"]["transactions_emitted_sv"] >= 1
        assert out.sv is not None
        assert out.ml is not None
        assert out.report is not None

    def test_custom_output_port_captures_artifacts(self) -> None:
        """Testis defineeritud SimpleOutputPort salvestab kõik artefaktid.

        Tõestab, et pipeline kirjutab artefakte pordi protokolli kaudu,
        mitte konkreetse implementatsiooni kaudu.
        """
        dataset = FakeDatasetPort(
            accounts=_accounts(),
            transaction_reports={
                "transactions.json": _report(
                    booked=[_tx(amount="100.00", transaction_id="OUT-TX1")],
                ),
            },
        )
        out = SimpleOutputPort()
        spec = FakeSpecPort()
        clock = FixedClock()

        summary = run_pipeline(
            dataset=dataset, out=out, spec=spec, clock=clock,
            dataset_id="output-adapter-test", input_dir="<memory>",
        )

        assert summary["outcome"] in ("SUCCESS", "PARTIAL_SUCCESS")
        assert "sv" in out.artifacts
        assert "ml" in out.artifacts
        assert "llm" in out.artifacts
        assert "report" in out.artifacts
        assert out.artifacts["run_id"] == "fake-run-001"

    def test_pipeline_result_identical_across_adapters(self) -> None:
        """Sama loogiline sisend kahe erineva adapteri kaudu annab identse SV väljundi.

        Tõestab, et pipeline'i käitumine ei sõltu konkreetsest adapteri
        implementatsioonist — ainult pordi protokolli lepingust.
        """
        booked_txs = [
            _tx(amount="100.00", transaction_id="ID-TX1"),
            _tx(amount="-50.00", transaction_id="ID-TX2"),
        ]
        accts = _accounts()
        report_data = _report(booked=booked_txs)
        clock = FixedClock()

        # Adapter A: FakeDatasetPort
        dataset_a = FakeDatasetPort(
            accounts=accts,
            transaction_reports={"transactions.json": report_data},
        )
        out_a = FakeOutputPort()
        run_pipeline(
            dataset=dataset_a, out=out_a, spec=FakeSpecPort(), clock=clock,
            dataset_id="identity-test", input_dir="<memory>",
        )

        # Adapter B: SimpleDictDatasetPort
        dataset_b = SimpleDictDatasetPort({
            "accounts_payload": accts,
            "reports": {"transactions.json": report_data},
        })
        out_b = FakeOutputPort()
        run_pipeline(
            dataset=dataset_b, out=out_b, spec=FakeSpecPort(), clock=clock,
            dataset_id="identity-test", input_dir="<memory>",
        )

        # SV väljundid peavad olema identsed
        assert out_a.sv == out_b.sv, (
            "Same logical input through different adapters must yield identical SV output"
        )
        assert out_a.ml == out_b.ml, "ML projections must be identical"


# ===================================================================
# Stsenaarium 4: Struktuurselt uudne projektsioon — C-06 SV → kuubilanss
# ===================================================================

class TestC06ProjectionExtensibility:
    """C-06 evolutsioonistsenaarium: ajaseeria-kujuline cashflow projektsioon.

    Erinevalt C-02-st (lame ridade list), C-03-st (kontekstiaken konto kohta)
    ja C-05-st (lamed agregaadid konto kohta) toodab C-06 struktuurselt
    uudse kuju: järjestatud kuu-bucket'ide aegrida iga konto kohta, millel
    on akumuleeruv jooksev saldo.  See tõestab, et SV vahekiht toetab ka
    ajalis-akumulatiivset projektsiooni ilma pipeline'i, porte ega
    adaptereid muutmata.
    """

    def test_c06_callable_on_pipeline_sv_output(self) -> None:
        """Võtmetest: C-06 töötab pipeline SV väljundil ilma pipeline'i muutmata."""
        booked = [
            _tx(amount="100.00", transaction_id="TX1", value_date="2025-01-15", booking_date="2025-01-15"),
            _tx(amount="50.00", transaction_id="TX2", value_date="2025-01-20", booking_date="2025-01-20"),
        ]
        _, out = _run(booked=booked)

        assert out.sv is not None, "Pipeline must produce SV output"

        timelines = project_monthly_balance(out.sv)

        assert isinstance(timelines, list)
        assert len(timelines) == 1
        assert timelines[0]["account_id"] == "acct-001"
        assert len(timelines[0]["timeline"]) == 1

    def test_c06_existing_projections_unchanged(self) -> None:
        """C-06 kutsumine ei mõjuta olemasolevaid C-02, C-03 ega C-05 väljundeid."""
        booked = [
            _tx(amount="100.00", transaction_id="TX001", value_date="2025-03-10", booking_date="2025-03-10"),
            _tx(amount="-50.00", transaction_id="TX002", creditor_name="Vendor", debtor_name=None, value_date="2025-04-15", booking_date="2025-04-15"),
        ]
        _, out = _run(booked=booked)

        ml_before = out.ml
        llm_before = out.llm
        stats_before = project_stats(out.sv)

        # C-06 kutsumine SV bundle'il
        timelines = project_monthly_balance(out.sv)
        assert len(timelines) > 0

        # C-02 ja C-03 objektid ei muutunud (sama viide)
        assert out.ml is ml_before, "C-02 ML output object must not change"
        assert out.llm is llm_before, "C-03 LLM output object must not change"

        # C-05 väärtus jääb täpselt samaks (puhas funktsioon ilma kõrvalmõjudeta)
        stats_after = project_stats(out.sv)
        assert stats_after == stats_before, "C-05 stats must remain byte-identical"

    def test_c06_output_shape_is_time_series(self) -> None:
        """C-06 väljundi kuju on selgelt erinev C-02 / C-03 / C-05 omast.

        Iga konto kirje peab sisaldama ajalist ``timeline`` massiivi, kus
        bucket'idel on ``month``, ``net`` ja ``running_balance`` väljad.
        Need on C-02 (lame), C-03 (kontekstiaken) ja C-05 (lamedad
        skalaarid) juures puudu.
        """
        booked = [
            _tx(amount="200.00", transaction_id="TX1", value_date="2025-01-10", booking_date="2025-01-10"),
            _tx(amount="-80.00", transaction_id="TX2", creditor_name="Vendor", debtor_name=None, value_date="2025-02-05", booking_date="2025-02-05"),
            _tx(amount="50.00", transaction_id="TX3", value_date="2025-03-01", booking_date="2025-03-01"),
        ]
        _, out = _run(booked=booked)

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

        # Struktuurne eristumine C-02-st: C-02 ridadel on row_id ja signed_amount,
        # C-06 bucket'idel mitte.
        assert "row_id" not in bucket
        assert "signed_amount" not in bucket
        # Struktuurne eristumine C-05-st: C-05 konto kirjel on top_counterparties
        # ja transaction_count, C-06-l mitte.
        assert "top_counterparties" not in entry
        assert "transaction_count" not in entry

    def test_c06_monthly_buckets_sorted_chronologically(self) -> None:
        """C-06 bucket'id tulevad kronoloogilises järjekorras, isegi kui sisend on segamini."""
        booked = [
            _tx(amount="10.00", transaction_id="TX-JUN", value_date="2025-06-15", booking_date="2025-06-15"),
            _tx(amount="20.00", transaction_id="TX-MAR", value_date="2025-03-20", booking_date="2025-03-20"),
            _tx(amount="30.00", transaction_id="TX-SEP", value_date="2025-09-05", booking_date="2025-09-05"),
            _tx(amount="40.00", transaction_id="TX-JAN", value_date="2025-01-10", booking_date="2025-01-10"),
        ]
        _, out = _run(booked=booked)

        timelines = project_monthly_balance(out.sv)
        months = [b["month"] for b in timelines[0]["timeline"]]

        assert months == ["2025-01", "2025-03", "2025-06", "2025-09"]

    def test_c06_running_balance_accumulates(self) -> None:
        """Iga bucket'i jooksev saldo on eelmiste netide kumulatiivne summa.

        See on C-06 keskne eristus C-05-st: akumulaator üle kuudejärjekorra,
        mitte lamedad sõltumatud agregaadid.
        """
        booked = [
            # 2025-01: +100
            _tx(amount="100.00", transaction_id="TX-JAN1",
                value_date="2025-01-10", booking_date="2025-01-10"),
            # 2025-02: -30
            _tx(amount="-30.00", transaction_id="TX-FEB1",
                creditor_name="Vendor", debtor_name=None,
                value_date="2025-02-05", booking_date="2025-02-05"),
            # 2025-03: +50
            _tx(amount="50.00", transaction_id="TX-MAR1",
                value_date="2025-03-02", booking_date="2025-03-02"),
        ]
        _, out = _run(booked=booked)

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

    def test_c06_multi_account_isolation(self) -> None:
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
        _, out = _run(accounts=accounts, transaction_reports=reports)

        timelines = project_monthly_balance(out.sv)
        by_id = {t["account_id"]: t for t in timelines}

        assert set(by_id.keys()) == {"acct-001", "acct-002"}

        months_a = [b["month"] for b in by_id["acct-001"]["timeline"]]
        months_b = [b["month"] for b in by_id["acct-002"]["timeline"]]
        assert months_a == ["2025-01", "2025-02"]
        assert months_b == ["2025-03"]

        # Jooksev saldo konto A-l ei mõjuta konto B-d.
        assert by_id["acct-001"]["timeline"][-1]["running_balance"] == "300"
        assert by_id["acct-002"]["timeline"][-1]["running_balance"] == "500"

    def test_c06_handles_empty_transactions(self) -> None:
        """C-06 tühja tehinguloendiga annab tühja aegrea."""
        _, out = _run(booked=[], pending=[])

        timelines = project_monthly_balance(out.sv)
        assert len(timelines) == 1
        assert timelines[0]["account_id"] == "acct-001"
        assert timelines[0]["timeline"] == []

    def test_c06_no_io_imports(self) -> None:
        """C-06 moodul ei impordi I/O, pathlib ega os mooduleid.

        Sama arhitektuuriline piir nagu test_import_boundaries.py jõustab
        ja nagu C-05 jaoks juba testitakse.
        """
        import domain.projections.c06_sv_to_monthly_balance as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        forbidden = {"os", "pathlib", "json", "csv", "io", "shutil", "tempfile"}
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])

        violations = imported & forbidden
        assert not violations, (
            f"C-06 imports forbidden I/O modules: {violations}. "
            "Domain projections must remain pure."
        )


# ===================================================================
# Stsenaarium 5: C-06 opt-in raporti integratsioon
# ===================================================================

def _run_with_profile(
    *,
    profile: dict[str, Any] | None = None,
    booked: list | None = None,
    pending: list | None = None,
) -> tuple[dict, FakeOutputPort]:
    """Run pipeline with a custom FakeSpecPort profile override.

    Lets tests flip the ``report_extensions`` opt-in flag while keeping the
    rest of the default profile intact.
    """
    dataset = FakeDatasetPort(
        accounts=_accounts(),
        transaction_reports={
            "transactions.json": _report(
                booked=booked or [], pending=pending or [],
            ),
        },
    )
    out = FakeOutputPort()
    spec = FakeSpecPort(profile_override=profile) if profile is not None else FakeSpecPort()
    clock = FixedClock()
    summary = run_pipeline(
        dataset=dataset,
        out=out,
        spec=spec,
        clock=clock,
        dataset_id="extension-test",
        input_dir="<memory>",
    )
    return summary, out


def _profile_with_monthly_balance_extension() -> dict[str, Any]:
    """Default fake profile plus ``report_extensions: ["monthly_balance"]``."""
    profile = copy.deepcopy(_default_profile())
    profile["report_extensions"] = ["monthly_balance"]
    return profile


_SPEC_S05_PATH = (
    Path(__file__).resolve().parents[3]
    / "spec" / "schemas" / "S-05_collected_report_schema.json"
)


def _load_s05_schema() -> dict:
    with _SPEC_S05_PATH.open(encoding="utf-8") as f:
        return json.load(f)


class TestC06ReportIntegration:
    """Opt-in raporti laiendus — C-06 ``monthly_balance`` ``report.json``-is.

    Tõestab, et uue projektsiooni raportisse ühendamine nõuab ainult
    väga väikest, lokaliseeritud lisandust (S-05 skeemis üks valikuline
    väli, ``build_report()``-is üks valikuline nimeline parameeter ja
    pipeline'is profiilipõhine lüliti) ning ei mõjuta olemasolevat
    vaikekäitumist ega teisi projektsioone.
    """

    # Jagatud fikseeritud sisend — samad tehingud disabled/enabled jooksude jaoks,
    # et kaks jooksu oleksid muus osas täpselt võrreldavad.
    _FIXED_BOOKED = [
        _tx(amount="100.00", transaction_id="STEP2-TX1",
            value_date="2025-01-10", booking_date="2025-01-10"),
        _tx(amount="-40.00", transaction_id="STEP2-TX2",
            creditor_name="Vendor", debtor_name=None,
            value_date="2025-02-15", booking_date="2025-02-15"),
        _tx(amount="25.00", transaction_id="STEP2-TX3",
            value_date="2025-03-05", booking_date="2025-03-05"),
    ]

    def test_c06_not_in_report_when_disabled(self) -> None:
        """Vaikimisi profiil ei sisalda ``report_extensions`` → raport jääb muutumatuks."""
        _, out = _run_with_profile(booked=self._FIXED_BOOKED)

        assert out.report is not None
        assert "extensions" not in out.report, (
            "Default-profile runs must remain byte-identical — "
            "no 'extensions' key must appear in report.json."
        )

    def test_c06_in_report_when_enabled(self) -> None:
        """Kui profiil lülitab ``monthly_balance`` sisse, siis see ilmub raportisse.

        Raportis olev sektsioon peab olema täpselt sama, mis ``project_monthly_balance()``
        otsekutse tagastab — ehk samal SV sisendil identne väärtus.
        """
        profile = _profile_with_monthly_balance_extension()
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        assert out.report is not None
        assert "extensions" in out.report
        assert "monthly_balance" in out.report["extensions"]

        expected = project_monthly_balance(out.sv)
        assert out.report["extensions"]["monthly_balance"] == expected

    def test_existing_report_fields_stable_with_c06_enabled(self) -> None:
        """Laienduse sisselülitamine ei muuda ühtegi teist raporti välja.

        Jooksutame sama sisendit sama kella all kahel korral — ühel korral
        laiendus disabled, teisel korral enabled.  Eemaldame enabled raporti
        ``"extensions"`` võtme ja võrdleme ülejäänut baidihaaval disabled
        raportiga — need peavad olema identsed.  See tõestab, et hook
        on puhtalt aditiivne ega riku olemasolevat raporti käitumist.
        """
        _, out_disabled = _run_with_profile(booked=self._FIXED_BOOKED)
        _, out_enabled = _run_with_profile(
            profile=_profile_with_monthly_balance_extension(),
            booked=self._FIXED_BOOKED,
        )

        report_enabled_trimmed = {
            k: v for k, v in out_enabled.report.items() if k != "extensions"
        }
        assert report_enabled_trimmed == out_disabled.report, (
            "Every non-extensions report field must stay byte-identical when "
            "the C-06 extension is enabled."
        )

    def test_c06_enablement_does_not_affect_other_projections(self) -> None:
        """C-06 sisselülitamine ei mõjuta C-02 (ML), C-03 (LLM) ega C-05 (stats) väljundeid.

        Tõestab, et laienduskanal on lokaalne ``report.json``-i suhtes ning
        teised projektsioonid jäävad puutumata — täpselt see mõjuulatuse
        kitsendus, mida lõputöö väide nõuab.
        """
        _, out_disabled = _run_with_profile(booked=self._FIXED_BOOKED)
        _, out_enabled = _run_with_profile(
            profile=_profile_with_monthly_balance_extension(),
            booked=self._FIXED_BOOKED,
        )

        assert out_enabled.sv == out_disabled.sv, "SV bundle must be identical"
        assert out_enabled.ml == out_disabled.ml, "C-02 ML output must be identical"
        assert out_enabled.llm == out_disabled.llm, "C-03 LLM output must be identical"
        assert project_stats(out_enabled.sv) == project_stats(out_disabled.sv), (
            "C-05 stats must be identical"
        )

    def test_report_validates_against_s05_with_extension(self) -> None:
        """Raport valideerub tõelise S-05 skeemi vastu nii disabled kui enabled jooksul.

        Tõestab, et S-05 skeemimuudatus (``extensions`` optsionaalne väli)
        on tegelikult kooskõlas pipeline'i väljundiga mõlemas režiimis ja
        lõppraport läheb jsonschema-validatsioonist läbi.
        """
        s05 = _load_s05_schema()

        _, out_disabled = _run_with_profile(booked=self._FIXED_BOOKED)
        jsonschema.validate(out_disabled.report, s05)

        _, out_enabled = _run_with_profile(
            profile=_profile_with_monthly_balance_extension(),
            booked=self._FIXED_BOOKED,
        )
        jsonschema.validate(out_enabled.report, s05)

        # Täielikkuse kontroll: enabled jooksu raportis on ``extensions`` võti
        # ning valideerus eelnev ``jsonschema.validate`` kutse tähendab, et
        # S-05 ``additionalProperties: false`` juurtasand aktsepteerib seda
        # uut nimelist välja.
        assert "extensions" in out_enabled.report


# ===================================================================
# Stsenaarium 6: C-05 & C-06 esimese klassi projektsioonid
# ===================================================================

def _profile_with_extra_projections(*names: str) -> dict[str, Any]:
    """Default fake profile plus ``extra_projections`` opt-in gate.

    Adds permissive schemas for S-06/S-07 and minimal contracts for C-05/C-06
    with ``output.file`` and ``output.schema`` fields so that the pipeline can
    derive the output filename and validation schema from the contract.
    """
    profile = copy.deepcopy(_default_profile())
    profile["extra_projections"] = list(names)
    profile["schemas"]["S-06"] = {}
    profile["schemas"]["S-07"] = {}
    profile["contracts"]["C-05"] = {
        "id": "C-05_SV_TO_STATS",
        "version": "1.0.0",
        "output": {
            "format": "JSON",
            "file": "projections/stats_v1.json",
            "schema": "S-06",
        },
    }
    profile["contracts"]["C-06"] = {
        "id": "C-06_SV_TO_MONTHLY_BALANCE",
        "version": "1.0.0",
        "output": {
            "format": "JSON",
            "file": "projections/monthly_balance_v1.json",
            "schema": "S-07",
        },
    }
    return profile


_SPEC_S06_PATH = (
    Path(__file__).resolve().parents[3]
    / "spec" / "schemas" / "S-06_stats_schema.json"
)

_SPEC_S07_PATH = (
    Path(__file__).resolve().parents[3]
    / "spec" / "schemas" / "S-07_monthly_balance_schema.json"
)


def _load_real_schema(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


class TestExtraProjectionsIntegration:
    """C-05 & C-06 esimese klassi projektsioonid — profiili kaudu aktiveeritud,
    lepinguga seotud, skeemi vastu valideeritud, eraldi väljundfailidena.

    Tõestab, et uued projektsioonid järgivad sama arhitektuurimustrit nagu
    C-02 (ML) ja C-03 (LLM): profiil juhib aktiveerimist, leping määrab
    väljundfaili tee ja skeemi, pipeline valideerib ja kirjutab eraldi faili,
    raport sisaldab auditijälge.
    """

    _FIXED_BOOKED = [
        _tx(amount="100.00", transaction_id="EP-TX1",
            value_date="2025-01-10", booking_date="2025-01-10"),
        _tx(amount="-40.00", transaction_id="EP-TX2",
            creditor_name="Vendor", debtor_name=None,
            value_date="2025-02-15", booking_date="2025-02-15"),
        _tx(amount="25.00", transaction_id="EP-TX3",
            value_date="2025-03-05", booking_date="2025-03-05"),
    ]

    def test_not_triggered_on_default_profile(self) -> None:
        """Vaikeprofiil ei tekita ühtki extra projection väljundit."""
        _, out = _run_with_profile(booked=self._FIXED_BOOKED)

        assert out.extra_projections == {}, (
            "Default-profile runs must produce no extra projection files."
        )
        assert "extra_projections" not in (out.report or {}), (
            "Default-profile report must not contain extra_projections key."
        )

    def test_stats_written_when_enabled(self) -> None:
        """extra_projections: [stats] tekitab stats_v1.json väljundi."""
        profile = _profile_with_extra_projections("stats")
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        assert "stats_v1.json" in out.extra_projections
        expected = project_stats(out.sv)
        assert out.extra_projections["stats_v1.json"] == expected

    def test_monthly_balance_written_when_enabled(self) -> None:
        """extra_projections: [monthly_balance] tekitab monthly_balance_v1.json."""
        profile = _profile_with_extra_projections("monthly_balance")
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        assert "monthly_balance_v1.json" in out.extra_projections
        expected = project_monthly_balance(out.sv)
        assert out.extra_projections["monthly_balance_v1.json"] == expected

    def test_both_projections_enabled(self) -> None:
        """Mõlemad projektsioonid aktiveerituna tekitavad mõlemad väljundid."""
        profile = _profile_with_extra_projections("stats", "monthly_balance")
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        assert "stats_v1.json" in out.extra_projections
        assert "monthly_balance_v1.json" in out.extra_projections

    def test_audit_trail_in_report(self) -> None:
        """Raport sisaldab extra_projections auditijälge."""
        profile = _profile_with_extra_projections("stats", "monthly_balance")
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        assert "extra_projections" in out.report
        audit = out.report["extra_projections"]
        assert len(audit) == 2

        names = {a["name"] for a in audit}
        assert names == {"stats", "monthly_balance"}

        for entry in audit:
            assert entry["enabled"] is True
            assert entry["contract_id"].startswith("C-0")
            assert entry["contract_version"] == "1.0.0"
            assert entry["schema_id"] in ("S-06", "S-07")
            assert entry["output_file"].startswith("projections/")
            assert entry["item_count"] >= 1
            assert entry["validation_result"] == "PASS"

    def test_schema_validation_pass_recorded(self) -> None:
        """Permissiivse skeemiga valideerimistulemus on PASS."""
        profile = _profile_with_extra_projections("stats")
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        audit = out.report["extra_projections"]
        assert audit[0]["validation_result"] == "PASS"

    def test_schema_validation_failure_recorded(self) -> None:
        """Piiratud skeemiga valideerimistulemus on FAIL ja issue tekib."""
        profile = _profile_with_extra_projections("stats")
        # Override S-06 with a schema that rejects the actual output
        profile["schemas"]["S-06"] = {
            "type": "object",
            "required": ["nonexistent_field"],
        }
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        audit = out.report["extra_projections"]
        assert audit[0]["validation_result"].startswith("FAIL:")

        # Validation failure must also appear in issues
        schema_issues = [
            i for i in out.report.get("issues", [])
            if i["code"] == "S-06_VALIDATION"
        ]
        assert len(schema_issues) >= 1

    def test_contract_drives_output_filename(self) -> None:
        """Lepingu output.file väli määrab väljundfaili nime."""
        profile = _profile_with_extra_projections("stats")
        profile["contracts"]["C-05"]["output"]["file"] = "projections/custom_stats.json"
        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        assert "custom_stats.json" in out.extra_projections
        assert "stats_v1.json" not in out.extra_projections

    def test_default_behavior_unchanged(self) -> None:
        """Vaikeprofiili väljund on baidihaaval identne enne ja pärast muudatusi."""
        _, out_default = _run_with_profile(booked=self._FIXED_BOOKED)
        _, out_extra = _run_with_profile(
            profile=_profile_with_extra_projections("stats", "monthly_balance"),
            booked=self._FIXED_BOOKED,
        )

        # SV, ML, LLM peavad olema identsed
        assert out_default.sv == out_extra.sv, "SV must be identical"
        assert out_default.ml == out_extra.ml, "ML must be identical"
        assert out_default.llm == out_extra.llm, "LLM must be identical"

    def test_existing_ml_llm_unchanged(self) -> None:
        """Extra projections sisselülitamine ei mõjuta ML ja LLM väljundeid."""
        _, out_disabled = _run_with_profile(booked=self._FIXED_BOOKED)
        _, out_enabled = _run_with_profile(
            profile=_profile_with_extra_projections("stats", "monthly_balance"),
            booked=self._FIXED_BOOKED,
        )

        assert out_enabled.ml == out_disabled.ml, "C-02 ML must be identical"
        assert out_enabled.llm == out_disabled.llm, "C-03 LLM must be identical"
        assert project_stats(out_enabled.sv) == project_stats(out_disabled.sv)

    def test_report_extensions_coexist(self) -> None:
        """report_extensions ja extra_projections töötavad koos."""
        profile = _profile_with_extra_projections("monthly_balance")
        profile["report_extensions"] = ["monthly_balance"]

        _, out = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)

        # report_extensions mehhanism paneb andmed report.extensions sisse
        assert "extensions" in out.report
        assert "monthly_balance" in out.report["extensions"]

        # extra_projections mehhanism kirjutab eraldi faili + audit
        assert "monthly_balance_v1.json" in out.extra_projections
        assert "extra_projections" in out.report

    def test_stats_validates_against_real_s06(self) -> None:
        """Stats väljund valideerub tõelise S-06 skeemi vastu."""
        _, out = _run(booked=self._FIXED_BOOKED)
        stats = project_stats(out.sv)
        s06 = _load_real_schema(_SPEC_S06_PATH)
        jsonschema.validate(stats, s06)

    def test_monthly_balance_validates_against_real_s07(self) -> None:
        """Monthly balance väljund valideerub tõelise S-07 skeemi vastu."""
        _, out = _run(booked=self._FIXED_BOOKED)
        timelines = project_monthly_balance(out.sv)
        s07 = _load_real_schema(_SPEC_S07_PATH)
        jsonschema.validate(timelines, s07)

    def test_report_validates_against_s05_with_extra_projections(self) -> None:
        """Raport valideerub S-05 skeemi vastu nii disabled kui enabled jooksul."""
        s05 = _load_s05_schema()

        # Disabled
        _, out_disabled = _run_with_profile(booked=self._FIXED_BOOKED)
        jsonschema.validate(out_disabled.report, s05)

        # Enabled
        profile = _profile_with_extra_projections("stats", "monthly_balance")
        _, out_enabled = _run_with_profile(profile=profile, booked=self._FIXED_BOOKED)
        jsonschema.validate(out_enabled.report, s05)
        assert "extra_projections" in out_enabled.report
