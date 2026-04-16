"""SLI/SLO testid adapteri pipeline'ile.

Iga testiklass vastab ühele teenustaseme indikaatorile (SLI) või
operatiivsele kontrollile (QC) ja kontrollib, kas pipeline täidab
vastava teenustaseme eesmärgi (SLO).

SLI definitsioonid, mõõtetasemed ja SLO sihtmärgid
---------------------------------------------------
SLI-1  Skeemikatvus           covered_priority_fields / all_priority_fields
                              Tase: spetsifikatsioon   SLO: ≥ 0.95

SLI-2  Valideerimise läbivus  passed_validation_total / input_records_total
       (standardiseeritud    Töötlusse võetud sisendtehingute osakaal, mis jääb
        vaheesitusse          pärast kaardistust, invariantide kontrolli ja
        jõudmise määr)        deduplikatsiooni standardiseeritud vaheesitusse alles.
                              Tase: jooksupõhine       SLO: ≥ 0.99 (puhas sisend)

SLI-3  Invariantide täituvus  invariant_correct_total / invariant_checked_total
       (invariant compliance  invariant_correct_total väheneb ERROR-rikkumiste,
        ratio)                deduplikatsioonis eemaldatud kirjete ja WARN-lipuga
                              alles jäävate kirjete võrra.
                              Mapping drops ei kuulu nimetajasse
                              (invariant_checked_total).
                              Tase: jooksupõhine       SLO: ≥ 0.999; critical == 0

SLI-4  Determinism            identsete väljunditega jooksud / kõik kordusjooksud
                              Tase: mitme jooksu võrdlus (N=5)
                              EI OLE report.json metrics väli

SLI-5  Auditijälje täielikkus olemasolevad nõutud auditiväljad / kõik nõutud auditiväljad
                              Tase: jooksupõhine       SLO: 100 %

SLI-6  Referentsjõudlus       mediaanne töötlusaeg referentsandmestikul
                              Tase: eraldi mõõtmine (1 proovijooks + 5 mõõdetud jooksu)
                              EI OLE report.json metrics väli

QC-2 Eemaldatud kirjete      dropped_details_count / dropped_total
       raporteeritavus        Tase: jooksupõhine       SLO: 100 %

Gate   Operatiivne värav      error_drop_ratio < 5 % → PARTIAL_SUCCESS; ≥ 5 % → FAIL
                              EI OLE SLI
"""

from __future__ import annotations

import time

import pytest

from application.pipeline import run_pipeline
from tests.fakes import FakeDatasetPort, FakeOutputPort, FakeSpecPort, FakeValidationPort, FixedClock
from tests.fakes.builders import make_accounts as _accounts, make_tx as _tx, make_report as _report


def _run(*, accounts: dict | None = None, booked: list | None = None, pending: list | None = None, clock: FixedClock | None = None) -> tuple[dict, FakeOutputPort]:
    """Käivita pipeline etteantud andmetega; tagasta (kokkuvõte, väljundport)."""
    dataset = FakeDatasetPort(
        accounts=accounts or _accounts(),
        transaction_reports={"transactions.json": _report(booked=booked or [], pending=pending or [])},
    )
    out = FakeOutputPort()
    spec = FakeSpecPort()
    _clock = clock or FixedClock()
    summary = run_pipeline(
        dataset=dataset,
        out=out,
        spec=spec,
        clock=_clock,
        validator=FakeValidationPort(),
        dataset_id="sli-slo-test",
        input_dir="<memory>",
    )
    return summary, out


# ---------------------------------------------------------------------------
# SLI-1: Skeemikatvus (prioriteetsete SV väljade katvus)
# SLO: ≥ 0.95 — C-01 peab katma vähemalt 95 % prioriteetsetest SV väljadest
# ---------------------------------------------------------------------------

class TestSLI1SchemaCoverage:
    """SLI-1 — skeemikatvus: prioriteetsete SV väljade katvus.

    SLI-1 = covered_priority_fields / all_priority_fields

    See on spetsifikatsioonitaseme näitaja, mis põhineb hooldataval
    katvusdeklaratsioonil (SLI1_FIELD_COVERAGE moodulis domain.report.ops).
    Näitaja ei sõltu konkreetsest andmestikust ega jooksust.
    """

    def test_sli1_metric_exists_in_report(self) -> None:
        """SLI-1 metrika peab olema report.metrics.sli1 all."""
        _, out = _run(booked=[_tx()])
        assert out.report is not None
        assert "sli1" in out.report["metrics"]

    def test_sli1_has_required_keys(self) -> None:
        """SLI-1 metrika peab sisaldama kõiki 3 nõutud välja."""
        _, out = _run(booked=[_tx()])
        sli1 = out.report["metrics"]["sli1"]
        assert "sli1_coverage_ratio" in sli1
        assert "priority_sv_fields_total" in sli1
        assert "covered_priority_sv_fields" in sli1

    def test_sli1_priority_fields_positive(self) -> None:
        """priority_sv_fields_total peab olema > 0."""
        _, out = _run(booked=[_tx()])
        assert out.report["metrics"]["sli1"]["priority_sv_fields_total"] > 0

    def test_sli1_covered_leq_total(self) -> None:
        """covered_priority_sv_fields <= priority_sv_fields_total."""
        _, out = _run(booked=[_tx()])
        sli1 = out.report["metrics"]["sli1"]
        assert sli1["covered_priority_sv_fields"] <= sli1["priority_sv_fields_total"]

    def test_sli1_ratio_in_unit_interval(self) -> None:
        """sli1_coverage_ratio peab olema vahemikus [0, 1]."""
        _, out = _run(booked=[_tx()])
        ratio = out.report["metrics"]["sli1"]["sli1_coverage_ratio"]
        assert 0.0 <= ratio <= 1.0

    def test_sli1_baseline_meets_slo(self) -> None:
        """Praeguse baasprofiiliga SLI-1 peab olema >= 0.95 (SLO)."""
        _, out = _run(booked=[_tx()])
        ratio = out.report["metrics"]["sli1"]["sli1_coverage_ratio"]
        assert ratio >= 0.95

    def test_sli1_ratio_decreases_when_field_uncovered(self) -> None:
        """Kui üks väli märgitakse katvamata, peab SLI-1 suhtarv langema."""
        from domain.report.ops import SLI1_FIELD_COVERAGE, compute_sli1_coverage

        baseline = compute_sli1_coverage()
        override = dict(SLI1_FIELD_COVERAGE)
        override["record_id"] = False
        reduced = compute_sli1_coverage(coverage_map=override)

        assert reduced["sli1_coverage_ratio"] < baseline["sli1_coverage_ratio"]
        assert reduced["covered_priority_sv_fields"] == baseline["covered_priority_sv_fields"] - 1
        assert reduced["priority_sv_fields_total"] == baseline["priority_sv_fields_total"]

    def test_sli1_in_pipeline_summary(self) -> None:
        """SLI-1 peab olema ka pipeline'i tagastatud summary.metrics all."""
        summary, _ = _run(booked=[_tx()])
        assert "sli1" in summary["metrics"]
        assert summary["metrics"]["sli1"]["sli1_coverage_ratio"] >= 0.95


class TestSLI1RuntimeCoverage:
    """SLI-1 runtime-katvus: C-01 päriselt emissiooni kontroll tegeliku SV pealt.

    Erinevalt ``SLI1_FIELD_COVERAGE`` deklaratsioonist loeb see reaalsetest
    väljundist — kui C-01 lakkab mõnda prioriteetset välja emiteerimast,
    siis runtime-katvus langeb ja test kukub. Deklaratiivne SLI-1
    jääks 1.0 peale, ei avastaks regressiooni.
    """

    @pytest.fixture(scope="class")
    def sv_output(self) -> dict:
        booked = [
            _tx(
                transaction_id="RT-001",
                amount="100.00",
                value_date="2025-06-01",
                booking_date="2025-06-01",
                debtor_name="Sender AS",
            ),
            _tx(
                transaction_id="RT-002",
                amount="50.25",
                value_date="2025-06-02",
                booking_date=None,
                debtor_name=None,
                creditor_name="Shop OÜ",
            ),
        ]
        _, out = _run(booked=booked)
        return out.sv

    def test_all_priority_fields_covered(self, sv_output: dict) -> None:
        from domain.report.ops import SLI1_FIELD_COVERAGE, derive_sli1_coverage_from_sv

        runtime = derive_sli1_coverage_from_sv(sv_output)
        uncovered = [f for f, ok in runtime.items() if not ok]
        assert not uncovered, (
            f"C-01 ei emiteeri neid prioriteetseid välju üheski tehingus: {uncovered}"
        )
        assert set(runtime.keys()) == set(SLI1_FIELD_COVERAGE.keys())

    def test_coverage_drops_when_field_removed(self, sv_output: dict) -> None:
        from domain.report.ops import derive_sli1_coverage_from_sv

        mutated = {
            **sv_output,
            "transactions": [
                {**tx, "record_id": None} for tx in sv_output["transactions"]
            ],
        }
        runtime = derive_sli1_coverage_from_sv(mutated)
        assert runtime["record_id"] is False


# ---------------------------------------------------------------------------
# Struktuurne väljundi terviklikkus (varem SLI-1 struktuurikontrollid)
# ---------------------------------------------------------------------------
# Need testid kontrollivad, et väljundartefaktid (SV, ML, LLM, raport)
# sisaldavad nõutud tipptaseme struktuuri ja võtmeid.  Need on kasulikud
# struktuurse terviklikkuse kontrollid, kuid EI OLE ametlik SLI-1 metrika.
# SLI-1 on skeemi/lepingu katvus (vt TestSLI1SchemaCoverage).
# ---------------------------------------------------------------------------

class TestStructuralOutputIntegrity:
    """Struktuurne väljundi terviklikkus — väljundartefaktid kannavad nõutud tipptaseme struktuuri.

    Need on struktuurse kohalolu ja kuju kontrollid SV, ML, LLM ja raporti
    artefaktidele. Need täiendavad, kuid on eraldi ametlikust SLI-1
    metrikast (skeemi/lepingu katvus).
    """

    @pytest.fixture(scope="class")
    def result(self) -> tuple[dict, FakeOutputPort]:
        return _run(booked=[_tx()])

    def test_sv_bundle_has_meta(self, result: tuple[dict, FakeOutputPort]) -> None:
        """SV bundle peab sisaldama 'meta' sektsiooni."""
        _, out = result
        assert out.sv is not None, "sv not written"
        assert "meta" in out.sv

    def test_sv_bundle_has_accounts(self, result: tuple[dict, FakeOutputPort]) -> None:
        """SV bundle peab loetlema töödeldud kontod."""
        _, out = result
        assert "accounts" in out.sv
        assert len(out.sv["accounts"]) == 1

    def test_sv_bundle_has_transactions(self, result: tuple[dict, FakeOutputPort]) -> None:
        """SV bundle peab sisaldama tehingute nimekirja."""
        _, out = result
        assert "transactions" in out.sv

    def test_ml_rows_have_required_fields(self, result: tuple[dict, FakeOutputPort]) -> None:
        """Iga ML rida peab kandma account_id, record_id, value_date, signed_amount, currency, direction."""
        _, out = result
        assert out.ml is not None and len(out.ml) > 0, "ml not written"
        required = {"account_id", "record_id", "value_date", "signed_amount", "currency", "direction"}
        for row in out.ml:
            missing = required - row.keys()
            assert not missing, f"ML row missing fields: {missing}"

    def test_llm_context_has_required_keys(self, result: tuple[dict, FakeOutputPort]) -> None:
        """LLM kontekst peab sisaldama 'meta' (konto metaandmed) ja 'tx' (tehingud) võtmeid."""
        _, out = result
        assert out.llm is not None, "llm not written"
        # Ühe konto korral on kontekst sõnastik võtmetega 'meta' ja 'tx'.
        # Mitme konto korral on see selliste sõnastike nimekiri.
        ctx = out.llm if isinstance(out.llm, list) else [out.llm]
        for entry in ctx:
            assert "meta" in entry, f"LLM entry missing 'meta': {list(entry.keys())}"
            assert "tx" in entry, f"LLM entry missing 'tx': {list(entry.keys())}"

    def test_report_has_outcome(self, result: tuple[dict, FakeOutputPort]) -> None:
        """Raport peab sisaldama 'outcome' sektsiooni koos status väljaga."""
        _, out = result
        assert out.report is not None, "report not written"
        assert "outcome" in out.report
        assert "status" in out.report["outcome"]

    def test_report_has_summary_counts(self, result: tuple[dict, FakeOutputPort]) -> None:
        """Raporti summary peab sisaldama loendureid kontode, tehingute, ml_rows, llm_contexts kohta."""
        _, out = result
        counts = out.report["summary"]["counts"]
        for field in ("accounts_total", "transactions_total", "transactions_emitted_sv", "transactions_dropped", "ml_rows", "llm_contexts"):
            assert field in counts, f"counts missing '{field}'"

    def test_report_has_by_severity(self, result: tuple[dict, FakeOutputPort]) -> None:
        """Raport peab sisaldama tõsiduse jaotust: CRITICAL, ERROR, WARN, INFO."""
        _, out = result
        by_sev = out.report["summary"]["by_severity"]
        for level in ("CRITICAL", "ERROR", "WARN", "INFO"):
            assert level in by_sev, f"by_severity missing '{level}'"

    def test_report_has_issues_list(self, result: tuple[dict, FakeOutputPort]) -> None:
        """Raportil peab olema issues[] nimekiri (võib olla tühi)."""
        _, out = result
        assert "issues" in out.report
        assert isinstance(out.report["issues"], list)

    def test_report_has_dropped_details(self, result: tuple[dict, FakeOutputPort]) -> None:
        """Raportil peab olema dropped_details[] nimekiri (võib olla tühi)."""
        _, out = result
        assert "dropped_details" in out.report

    # -- Raporti metaandmete olemasolu kontrollid --

    def test_report_run_id_present(self, result: tuple[dict, FakeOutputPort]) -> None:
        """report.run peab kandma run_id välja (jooksu identifitseerimiseks)."""
        _, out = result
        assert "run_id" in out.report["run"]
        assert out.report["run"]["run_id"] != ""

    def test_report_created_at_utc_present(self, result: tuple[dict, FakeOutputPort]) -> None:
        """report.run peab kandma created_at_utc ajatemplit."""
        _, out = result
        assert "created_at_utc" in out.report["run"]
        assert out.report["run"]["created_at_utc"] != ""

    def test_report_schema_version_present(self, result: tuple[dict, FakeOutputPort]) -> None:
        """Raport peab kandma report_schema_version välja juuretasemel."""
        _, out = result
        assert "report_schema_version" in out.report
        assert out.report["report_schema_version"] != ""
        assert isinstance(out.report["dropped_details"], list)


# ---------------------------------------------------------------------------
# SLI-2: Valideerimise läbivus (validation pass-through ratio)
# SLO: ≥ 0.99 puhaste datasettide korral; vea-datasettidel kirjeldav metrika
# ---------------------------------------------------------------------------

class TestSLI2ValidationPassThrough:
    """SLI-2 — töötlusse võetud sisendtehingute osakaal, mis jääb pärast
    kaardistust, invariantide kontrolli ja deduplikatsiooni standardiseeritud
    vaheesitusse alles.

    SLI-2 = passed_validation_total / input_records_total
    where:
      input_records_total    = transactions_total  (all raw input tx)
      passed_validation_total = transactions_emitted_sv
          (kirjed, mis jäävad alles pärast kaardistust, invariantide
           kontrolli ja deduplikatsiooni)
    """

    def test_clean_input_pass_through_ratio_is_one(self) -> None:
        """Puhas sisend annab SLI-2 = 1.0 (kõik kirjed läbivad valideerimise)."""
        summary, _ = _run(booked=[_tx()])
        ratio = summary["metrics"]["sli2"]["validation_pass_through_ratio"]
        assert ratio == 1.0

    def test_partial_drops_ratio_between_zero_and_one(self) -> None:
        """Osaliste langetustega peab SLI-2 olema vahemikus (0, 1)."""
        bad = {
            "transactionAmount": {"amount": "50.00", "currency": "EUR"},
            "transactionId": "TX-NO-DATE",
            "debtorName": "Someone",
        }
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(4)]
        summary, _ = _run(booked=good + [bad])
        ratio = summary["metrics"]["sli2"]["validation_pass_through_ratio"]
        assert 0 < ratio < 1
        # 4 good out of 5 total → 0.8
        assert ratio == round(4 / 5, 4)

    def test_all_dropped_ratio_is_zero(self) -> None:
        """Kõigi kirjete langetamisel peab SLI-2 olema 0.0."""
        bad = {
            "transactionAmount": {"amount": "50.00", "currency": "EUR"},
            "transactionId": "TX-NO-DATE",
        }
        summary, _ = _run(booked=[bad])
        ratio = summary["metrics"]["sli2"]["validation_pass_through_ratio"]
        assert ratio == 0.0

    def test_ratio_equals_emitted_over_total(self) -> None:
        """SLI-2 peab võrduma transactions_emitted_sv / transactions_total."""
        bad = _tx(currency="xx", transaction_id="BAD")
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(9)]
        summary, _ = _run(booked=good + [bad])
        counts = summary["counts"]
        expected = round(counts["transactions_emitted_sv"] / counts["transactions_total"], 4)
        assert summary["metrics"]["sli2"]["validation_pass_through_ratio"] == expected

    def test_ratio_consistent_with_dropped_total(self) -> None:
        """SLI-2 + dropped/total peab andma 1.0 (identity check)."""
        bad = _tx(currency="xx", transaction_id="BAD")
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(3)]
        summary, _ = _run(booked=good + [bad])
        counts = summary["counts"]
        pass_ratio = summary["metrics"]["sli2"]["validation_pass_through_ratio"]
        drop_ratio = counts["transactions_dropped"] / counts["transactions_total"]
        assert abs(pass_ratio + drop_ratio - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# QC-2: Langetuste raporteerimine (operational drop-reporting coverage)
# SLO: 100 % langetustest ilmub report.dropped_details[] all
# ---------------------------------------------------------------------------

class TestQC2DropReporting:
    """QC-2— kõik langetused kajastatakse dropped_details[] all (operational control).

    This was previously labeled SLI-2. Renamed to QC-2to restore the original
    SLI-2 meaning (validation pass-through ratio).
    """

    def test_valid_input_produces_no_issues(self) -> None:
        """Skeemi-kehtiv sisend ei tohi tekitada ühtegi issue't raportis."""
        summary, _ = _run(booked=[_tx()])
        assert summary["issues"] == []

    def test_valid_input_outcome_is_success(self) -> None:
        """Täiesti puhas sisend peab andma SUCCESS staatuse."""
        summary, _ = _run(booked=[_tx()])
        assert summary["outcome"] == "SUCCESS"

    def test_missing_value_date_produces_issue(self) -> None:
        """Puuduva valueDate-ga tehing peab ilmuma dropped_details[] alla."""
        bad = {
            "transactionAmount": {"amount": "50.00", "currency": "EUR"},
            "transactionId": "TX-NO-DATE",
            "debtorName": "Someone",
        }
        summary, _ = _run(booked=[bad])
        assert len(summary["dropped_details"]) == 1

    def test_missing_value_date_drop_reason_contains_valuedate(self) -> None:
        """Puuduva valueDate langetuspõhjus peab viitama valueDate puudumisele."""
        bad = {
            "transactionAmount": {"amount": "50.00", "currency": "EUR"},
            "transactionId": "TX-NO-DATE",
            "debtorName": "Someone",
        }
        summary, _ = _run(booked=[bad])
        drop_reason = summary["dropped_details"][0]["drop_reason"]
        assert "valueDate" in drop_reason or "value_date" in drop_reason.lower()

    def test_invalid_transaction_is_captured_in_dropped_details(self) -> None:
        """Standardiseerimatu tehing peab ilmuma dropped_details[] alla.

        Kaardistamisetapi langetused (nt puuduv valueDate) salvestatakse
        dropped_details[] alla, mitte by_severity alla, kuna need toimuvad
        enne invariantide kontrollietappi. Tulemus on FAIL (100 % drop-suhe > 5 %).
        """
        bad = {
            "transactionAmount": {"amount": "50.00", "currency": "EUR"},
            "transactionId": "TX-NO-DATE",
        }
        summary, _ = _run(booked=[bad])
        assert summary["counts"]["transactions_dropped"] > 0
        assert len(summary["dropped_details"]) > 0

    def test_qc2_all_drops_reported_clean_input(self) -> None:
        """Puhas sisend → QC-2all_drops_reported == True, ratio == 1.0."""
        summary, _ = _run(booked=[_tx()])
        qc2 = summary["metrics"]["qc2"]
        assert qc2["all_drops_reported"] is True
        assert qc2["drop_reporting_ratio"] == 1.0

    def test_qc2_all_drops_reported_with_drops(self) -> None:
        """Langetustega sisend → QC-2all_drops_reported == True (kõik kajastatud)."""
        bad = _tx(currency="xx", transaction_id="BAD")
        summary, _ = _run(booked=[_tx(), bad])
        qc2 = summary["metrics"]["qc2"]
        assert qc2["all_drops_reported"] is True
        assert qc2["drop_reporting_ratio"] == 1.0


# ---------------------------------------------------------------------------
# SLI-3: Invariantide täituvus (invariant compliance ratio)
# SLO: ≥ 0.999 puhaste datasettide korral; critical == 0
# ---------------------------------------------------------------------------

class TestSLI3InvariantCompliance:
    """SLI-3 — invariantide vastavuse suhtarv (invariant compliance ratio).

    SLI-3 = invariant_correct_total / invariant_checked_total

    invariant_correct_total väheneb:
      − ERROR-taseme invariantrikkumistega langetatud kirjete võrra,
      − deduplikatsioonis (INV-09) eemaldatud kirjete võrra,
      − WARN-lipuga alles jäävate kirjete võrra.

    Mapping drops (Stage 2 ebaõnnestumised) ei kuulu nimetajasse
    (invariant_checked_total), sest need kirjed ei jõua kunagi
    Stage 4 invariantide kontrollini.
    """

    def test_inv01_bad_currency_drops_transaction(self) -> None:
        """INV-01: vale valuutaformaadiga tehing peab langetatama (ERROR)."""
        bad = _tx(currency="xx")  # väiketähed — ei vasta [A-Z]{3}
        summary, _ = _run(booked=[_tx(), bad])
        assert summary["counts"]["transactions_dropped"] >= 1

    def test_inv02_missing_value_date_drops_transaction(self) -> None:
        """INV-02: puuduv valueDate peab põhjustama tehingu langetamise."""
        bad = {
            "transactionAmount": {"amount": "10.00", "currency": "EUR"},
            "transactionId": "TX-NODATE",
            "debtorName": "Ghost",
        }
        summary, _ = _run(booked=[_tx(), _tx(transaction_id="TX002", amount="20.00"), bad])
        assert summary["counts"]["transactions_dropped"] >= 1

    def test_inv09_duplicate_is_deduplicated(self) -> None:
        """INV-09: identsed tehingud peavad olema deduplitseeritud; üks säilitatakse."""
        dup = _tx(amount="77.77", value_date="2025-09-09", booking_date="2025-09-09",
                  debtor_name="DupSender", transaction_id="DUP")
        summary, out = _run(booked=[dup, dup])
        assert out.sv is not None
        assert len(out.sv["transactions"]) == 1

    def test_inv09_duplicate_appears_in_dropped_details(self) -> None:
        """INV-09: langetatud duplikaat peab ilmuma report.dropped_details[] alla."""
        dup = _tx(amount="77.77", value_date="2025-09-09", booking_date="2025-09-09",
                  debtor_name="DupSender", transaction_id="DUP")
        summary, _ = _run(booked=[dup, dup])
        reasons = [d["drop_reason"] for d in summary["dropped_details"]]
        assert any("INV-09" in r or "duplicate" in r.lower() for r in reasons)

    def test_inv04_bad_booking_date_keeps_transaction_as_warn(self) -> None:
        """INV-04: vigane bookingDate on WARN — tehingut ei tohi langetada."""
        t = {
            "transactionAmount": {"amount": "30.00", "currency": "EUR"},
            "valueDate": "2025-07-01",
            "bookingDate": "not-a-date",
            "debtorName": "WarnSender",
            "debtorAccount": {"iban": "NL91ABNA0417164300"},
            "transactionId": "TX-WARN",
        }
        summary, _ = _run(booked=[t])
        assert summary["counts"]["transactions_dropped"] == 0
        assert summary["counts"]["transactions_emitted_sv"] == 1

    def test_dropped_count_matches_dropped_details(self) -> None:
        """summary.counts.transactions_dropped peab võrduma len(dropped_details)."""
        bad = _tx(currency="xx", transaction_id="BAD-CUR")
        summary, _ = _run(booked=[_tx(), bad])
        assert summary["counts"]["transactions_dropped"] == len(summary["dropped_details"])

    def test_clean_run_sli3_is_one(self) -> None:
        """Puhas jooks: SLI-3 invariant compliance ratio == 1.0, critical == 0."""
        good = [_tx(transaction_id=f"T{i}", amount=str(10 + i)) for i in range(5)]
        summary, _ = _run(booked=good)
        sli3 = summary["metrics"]["sli3"]
        assert sli3["invariant_compliance_ratio"] == 1.0
        assert sli3["invariant_checked_total"] == 5
        assert sli3["invariant_correct_total"] == 5
        assert sli3["critical_invariant_violations_total"] == 0

    def test_error_drops_reduce_compliance_ratio(self) -> None:
        """ERROR invariant drop vähendab SLI-3 suhtarvu."""
        bad = _tx(currency="xx", transaction_id="BAD")
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(9)]
        summary, _ = _run(booked=good + [bad])
        sli3 = summary["metrics"]["sli3"]
        # 10 checked, 1 ERROR drop → 9 correct → ratio = 0.9
        assert sli3["invariant_checked_total"] == 10
        assert sli3["critical_invariant_violations_total"] == 1
        assert sli3["invariant_compliance_ratio"] == 0.9

    def test_warn_flags_reduce_compliance_ratio(self) -> None:
        """WARN invariant flag (INV-04) vähendab SLI-3 suhtarvu, kuigi tehing jääb alles."""
        warn_tx = {
            "transactionAmount": {"amount": "30.00", "currency": "EUR"},
            "valueDate": "2025-07-01",
            "bookingDate": "not-a-date",
            "debtorName": "WarnSender",
            "debtorAccount": {"iban": "NL91ABNA0417164300"},
            "transactionId": "TX-WARN",
        }
        good = _tx(transaction_id="G1", amount="10.00")
        summary, _ = _run(booked=[good, warn_tx])
        sli3 = summary["metrics"]["sli3"]
        # 2 checked, 1 WARN flagged → 1 correct → ratio = 0.5
        assert sli3["invariant_checked_total"] == 2
        assert sli3["invariant_correct_total"] == 1
        assert sli3["invariant_compliance_ratio"] == 0.5
        assert sli3["critical_invariant_violations_total"] == 0

    def test_dedupe_drops_reduce_compliance_ratio(self) -> None:
        """INV-09 dedupe drops vähendavad SLI-3 suhtarvu."""
        dup = _tx(amount="77.77", value_date="2025-09-09", booking_date="2025-09-09",
                  debtor_name="DupSender", transaction_id="DUP")
        good = _tx(transaction_id="G1", amount="10.00")
        summary, _ = _run(booked=[good, dup, dup])
        sli3 = summary["metrics"]["sli3"]
        # 3 checked, 1 dedupe drop → 2 correct → ratio ≈ 0.6667
        assert sli3["invariant_checked_total"] == 3
        assert sli3["invariant_correct_total"] == 2
        assert sli3["critical_invariant_violations_total"] == 0

    def test_invariant_correct_total_non_negative(self) -> None:
        """invariant_correct_total ei tohi kunagi olla negatiivne."""
        # All records are bad → invariant_correct_total == 0
        bad1 = _tx(currency="xx", transaction_id="BAD1", amount="10.00")
        bad2 = _tx(currency="yy", transaction_id="BAD2", amount="20.00")
        summary, _ = _run(booked=[bad1, bad2])
        sli3 = summary["metrics"]["sli3"]
        assert sli3["invariant_correct_total"] >= 0
        assert sli3["invariant_correct_total"] == 0
        assert sli3["invariant_compliance_ratio"] == 0.0

    def test_mapping_drops_excluded_from_sli3_denominator(self) -> None:
        """Mapping drops (Stage 2) ei tohi mõjutada SLI-3 nimetajat.

        A record that fails mapping (missing transactionAmount) never reaches
        Stage 4 invariant checking, so invariant_checked_total must not include it.
        """
        good = _tx(transaction_id="G1", amount="10.00")
        # Missing transactionAmount → mapping drop in Stage 2
        mapping_drop = {
            "transactionId": "MAP-DROP",
            "valueDate": "2025-06-01",
            "debtorName": "Ghost",
            # no transactionAmount → fails mapping
        }
        summary, _ = _run(booked=[good, mapping_drop])
        sli3 = summary["metrics"]["sli3"]
        # Only the good record reaches Stage 4
        assert sli3["invariant_checked_total"] == 1
        assert sli3["invariant_correct_total"] == 1
        assert sli3["invariant_compliance_ratio"] == 1.0
        # But the mapping drop still shows up in overall report counts
        assert summary["counts"]["transactions_dropped"] >= 1

    def test_dedupe_exact_ratio(self) -> None:
        """INV-09 dedupe: 3 checked, 1 dedupe drop → ratio = 0.6667."""
        dup = _tx(amount="77.77", value_date="2025-09-09", booking_date="2025-09-09",
                  debtor_name="DupSender", transaction_id="DUP")
        good = _tx(transaction_id="G1", amount="10.00")
        summary, _ = _run(booked=[good, dup, dup])
        sli3 = summary["metrics"]["sli3"]
        assert sli3["invariant_checked_total"] == 3
        assert sli3["invariant_correct_total"] == 2
        assert sli3["invariant_compliance_ratio"] == 0.6667
        assert sli3["critical_invariant_violations_total"] == 0


# ---------------------------------------------------------------------------
# Gate: Operatiivne kvaliteedivärav (ei ole SLI)
# SLO: error_drop_ratio < 5 % → PARTIAL_SUCCESS; ≥ 5 % → FAIL
# ---------------------------------------------------------------------------

class TestGateFailPolicy:
    """Gate — operatiivne kvaliteedivärav (vea-drop lävend, ei ole SLI)."""

    def test_gate_error_drop_ratio_in_metrics(self) -> None:
        """Gate metrikad peavad ilmuma report.metrics.gate alla."""
        bad = _tx(currency="xx", transaction_id="BAD")
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(9)]
        summary, _ = _run(booked=good + [bad])
        gate = summary["metrics"]["gate"]
        assert "error_drop_ratio" in gate
        assert "error_drops" in gate
        assert gate["error_drops"] == 1

    def test_below_5pct_error_rate_is_partial_success(self) -> None:
        """Vigade suhe alla 5 % peab andma PARTIAL_SUCCESS, mitte FAIL."""
        # 1 vigane 21-st kokku ≈ 4,8 % < 5 %
        bad = _tx(currency="xx", transaction_id="BAD")
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(20)]
        summary, _ = _run(booked=good + [bad])
        assert summary["outcome"] == "PARTIAL_SUCCESS"

    def test_at_or_above_5pct_error_rate_is_fail(self) -> None:
        """Vigade suhe 5 % või üle selle peab andma FAIL."""
        # 1 vigane 10-st = 10 % → FAIL
        bad = _tx(currency="xx", transaction_id="BAD")
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(9)]
        summary, _ = _run(booked=good + [bad])
        assert summary["outcome"] == "FAIL"

    def test_above_5pct_with_bad_currency(self) -> None:
        """INV-01: 1 vigane tehing 11-st on ~9 % → FAIL (gate error_drop_ratio > 5 %)."""
        bad = _tx(currency="xx", transaction_id="BAD")
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(10)]
        # 1 vigane / 11 kokku ≈ 9 % > 5 % → FAIL
        summary, _ = _run(booked=good + [bad])
        assert summary["outcome"] == "FAIL"

    def test_zero_errors_clean_run_is_success(self) -> None:
        """Jooks ilma vigadeta peab andma SUCCESS."""
        good = [_tx(transaction_id=f"T{i}", amount=str(10 + i)) for i in range(5)]
        summary, _ = _run(booked=good)
        assert summary["outcome"] == "SUCCESS"
        gate = summary["metrics"]["gate"]
        assert gate["error_drop_ratio"] == 0.0
        assert gate["error_drops"] == 0

    def test_gate_metrics_consistent_with_outcome(self) -> None:
        """Gate metrikad ja determine_outcome() kasutavad sama loendusloogikat.

        Both use count_error_drops().  This test verifies that:
        - gate.error_drops matches the count implied by the outcome
        - gate.error_drop_ratio == error_drops / input_records_total
        """
        # Mix: 1 ERROR invariant drop + 1 mapping drop (no transactionAmount)
        bad_inv = _tx(currency="xx", transaction_id="BAD-INV", amount="10.00")
        mapping_drop = {
            "transactionId": "MAP-DROP",
            "valueDate": "2025-06-01",
            "debtorName": "Ghost",
        }
        good = [_tx(transaction_id=f"G{i}", amount=str(10 + i)) for i in range(8)]
        summary, _ = _run(booked=good + [bad_inv, mapping_drop])
        gate = summary["metrics"]["gate"]
        total_raw = summary["counts"]["transactions_total"]
        # 2 error drops (1 invariant ERROR + 1 mapping drop) out of 10 total = 20%
        assert gate["error_drops"] == 2
        assert gate["error_drop_ratio"] == round(2 / total_raw, 4)
        # 20% > 5% → must be FAIL
        assert summary["outcome"] == "FAIL"
        assert gate["error_drop_ratio"] > 0.05


# ---------------------------------------------------------------------------
# SLI-4: Determinism
# SLO: 5 identset jooksu sama fikseeritud kellaga toodavad identsed väljundid
# ---------------------------------------------------------------------------
#
# SLI-4 = identsete väljundartefaktidega kordusjooksud / kõik kordusjooksud
#
# SLI-4 ei ole ühe jooksu report.json metrics väli.
# SLI-4 on näitaja, mida hinnatakse mitme kordusjooksu alusel.
# Sama sisend + sama konfiguratsioon + fikseeritud kell peavad andma
# identsed väljundartefaktid.
# ---------------------------------------------------------------------------

_SLI4_N_RUNS = 5


def _run_determinism_suite(
    booked: list[dict],
    n: int = _SLI4_N_RUNS,
) -> list[FakeOutputPort]:
    """Keskne SLI-4 helper: käivitab pipeline n korda sama kellaga.

    Tagastab n FakeOutputPort objekti, mille artefakte saab võrrelda.
    """
    clock = FixedClock(fixed_utc="2026-03-01T12:00:00Z", fixed_run_id="det-run-42")
    outputs: list[FakeOutputPort] = []
    for _ in range(n):
        _, out = _run(booked=booked, clock=clock)
        outputs.append(out)
    return outputs


class TestSLI4Determinism:
    """SLI-4 — determinism: 5 kordusjooksu sama sisendi ja kellaga peavad
    andma identsed väljundartefaktid.

    SLI-4 = identsete väljundartefaktidega kordusjooksud / kõik kordusjooksud

    See ei ole ühe jooksu report.json metrics väli, vaid mitme kordusjooksu
    alusel hinnatav näitaja.
    """

    @pytest.fixture(scope="class")
    def five_runs(self) -> list[FakeOutputPort]:
        booked = [
            _tx(amount="100.00", transaction_id="TX1"),
            _tx(amount="200.00", transaction_id="TX2", debtor_name=None, creditor_name="Shop"),
        ]
        return _run_determinism_suite(booked, n=_SLI4_N_RUNS)

    def test_sv_identical_across_all_runs(self, five_runs: list[FakeOutputPort]) -> None:
        """SV bundle peab olema identne kõigi 5 jooksu vahel."""
        ref = five_runs[0].sv
        for i, out in enumerate(five_runs[1:], start=2):
            assert out.sv == ref, f"SV differs in run {i} vs run 1"

    def test_ml_identical_across_all_runs(self, five_runs: list[FakeOutputPort]) -> None:
        """ML read peavad olema identsed kõigi 5 jooksu vahel."""
        ref = five_runs[0].ml
        for i, out in enumerate(five_runs[1:], start=2):
            assert out.ml == ref, f"ML differs in run {i} vs run 1"

    def test_llm_identical_across_all_runs(self, five_runs: list[FakeOutputPort]) -> None:
        """LLM kontekst peab olema identne kõigi 5 jooksu vahel."""
        ref = five_runs[0].llm
        for i, out in enumerate(five_runs[1:], start=2):
            assert out.llm == ref, f"LLM differs in run {i} vs run 1"

    def test_report_identical_across_all_runs(self, five_runs: list[FakeOutputPort]) -> None:
        """Raport peab olema identne kõigi 5 jooksu vahel.

        Report.json on determinismi seisukohalt täielikult stabiilne, sest:
        - run_id ja created_at_utc tulevad FixedClock-ilt (ei muutu jooksude vahel),
        - kõik loendid, metrikad ja issues tekivad deterministlikust domeeniloogikast,
        - puuduvad hostispetsiifilised, juhuslikud või kellast sõltuvad väljad.

        Seetõttu võrreldakse tervet report.json artefakti, mitte normaliseeritud alamhulka.
        """
        ref = five_runs[0].report
        for i, out in enumerate(five_runs[1:], start=2):
            assert out.report == ref, f"Report differs in run {i} vs run 1"

    def test_run_id_is_fixed(self, five_runs: list[FakeOutputPort]) -> None:
        """run_id peab tulema kellalt, mitte juhuslikust generaatorist."""
        for out in five_runs:
            assert out.run_id == "det-run-42"

    def test_created_at_is_fixed(self, five_runs: list[FakeOutputPort]) -> None:
        """created_at_utc peab tulema kellalt, mitte süsteemiajalt."""
        for out in five_runs:
            assert out.created_at_utc == "2026-03-01T12:00:00Z"

    def test_all_five_runs_executed(self, five_runs: list[FakeOutputPort]) -> None:
        """Kontroll, et tõepoolest käivitati 5 jooksu."""
        assert len(five_runs) == _SLI4_N_RUNS


# ---------------------------------------------------------------------------
# SLI-4: Determinism — byte-level via FS adapter
# ---------------------------------------------------------------------------
#
# Sama SLO, aga mõõdetud serialiseeritud failide SHA-256 võrdlusega. See testib
# ka FS-adaptereid (kirjutamise kanooniline järjestus, reavahetused, kodeering),
# mida in-memory dict-võrdlus ei kata.
# ---------------------------------------------------------------------------

import hashlib
from pathlib import Path as _Path

from entrypoints.wiring_fs import run_pipeline_fs as _run_pipeline_fs

_SLI4_FS_DATASET = "D1_synth_valid_small"
_SLI4_FS_ARTIFACTS = [
    "sv.json",
    "report.json",
    "projections/ml_v1.csv",
    "projections/llm_context_v1.json",
]


def _sha256(path: _Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class TestSLI4DeterminismBytes:
    """SLI-4 bait-tasemel: 5 FS-baasilist jooksu, võrreldakse SHA-256 räsisid."""

    @pytest.fixture(scope="class")
    def run_hashes(self, tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, str]]:
        project_root = _Path(__file__).resolve().parents[3]
        data_dir = project_root / "datasets" / _SLI4_FS_DATASET
        spec_dir = project_root / "spec"

        hashes: list[dict[str, str]] = []
        for i in range(_SLI4_N_RUNS):
            out_dir = tmp_path_factory.mktemp(f"sli4_fs_run_{i}")
            summary = _run_pipeline_fs(
                data_dir=data_dir,
                output_dir=out_dir,
                spec_dir=spec_dir,
                run_id="sli4-byte-run",
                created_at_utc="2026-03-01T12:00:00Z",
            )
            run_folder = _Path(summary["run_folder"])
            hashes.append({
                art: _sha256(run_folder / art)
                for art in _SLI4_FS_ARTIFACTS
            })
        return hashes

    @pytest.mark.parametrize("artifact", _SLI4_FS_ARTIFACTS)
    def test_artifact_byte_identical_across_runs(
        self, run_hashes: list[dict[str, str]], artifact: str,
    ) -> None:
        baseline = run_hashes[0][artifact]
        for i, run in enumerate(run_hashes[1:], start=2):
            assert run[artifact] == baseline, (
                f"{artifact} baidi-tasemel erineb jooksus {i} (run1={baseline[:12]}..., "
                f"run{i}={run[artifact][:12]}...)"
            )

    def test_five_runs_executed(self, run_hashes: list[dict[str, str]]) -> None:
        assert len(run_hashes) == _SLI4_N_RUNS


# ---------------------------------------------------------------------------
# SLI-5: Auditijälje täielikkus
# SLO: 100 % jooksudest sisaldab kõiki nõutud auditivälju
# ---------------------------------------------------------------------------
#
# SLI-5 = olemasolevad nõutud auditiväljad / kõik nõutud auditiväljad
#
# SLI-5 on jooksupõhine näitaja.  See kontrollib, et iga jooks kannab
# raportis kõiki taastoodetavuse ja auditeeritavuse jaoks nõutud
# metaandmeid.
#
# Miinimumnõutud auditiväljad:
#   sv_schema_version, mapping_version, ruleset_version, adapter_version
#
# Soovitavad lisaväljad:
#   spec_lock_sha256, input_fingerprint, output_artifact_hashes
# ---------------------------------------------------------------------------

class TestSLI5AuditTrailCompleteness:
    """SLI-5 — auditijälje täielikkus: nõutud auditiväljad report.run sektsioonis.

    SLI-5 = sisuliselt olemasolevad nõutud auditiväljad / kõik nõutud auditiväljad

    Kohustuslik auditiväli loetakse sisuliselt olevaks ainult siis, kui:
    - väli on report.run sektsioonis olemas,
    - väärtus ei ole None,
    - väärtus ei ole tühi ega ainult tühikutest koosnev string.
    """

    @pytest.fixture(scope="class")
    def report(self) -> dict:
        _, out = _run(booked=[_tx()])
        assert out.report is not None
        return out.report

    # -- Täisvastavus: kõik väljad olemas ja mittetühjad --

    def test_sli5_all_required_audit_fields_present(self, report: dict) -> None:
        """SLI-5: kõik 4 kohustuslikku auditivälja peavad olema report.run sektsioonis
        ja sisuliselt mittetühjad."""
        from domain.report.ops import SLI5_REQUIRED_AUDIT_FIELDS
        run_section = report["run"]
        for field in SLI5_REQUIRED_AUDIT_FIELDS:
            assert field in run_section, f"SLI-5: kohustuslik auditiväli '{field}' puudub report.run-ist"
            value = run_section[field]
            assert value is not None, f"SLI-5: auditiväli '{field}' on None"
            assert isinstance(value, str) and value.strip() != "", (
                f"SLI-5: auditiväli '{field}' on tühi või ainult tühikutest koosnev"
            )

    def test_sli5_completeness_ratio_is_one(self, report: dict) -> None:
        """SLI-5: auditijälje täielikkuse suhtarv peab olema 1.0 kui kõik väljad on olemas."""
        from domain.report.ops import compute_sli5_audit_completeness
        result = compute_sli5_audit_completeness(report)
        assert result["sli5_audit_completeness_ratio"] == 1.0
        assert result["required_fields_present"] == result["required_fields_total"]

    # -- Puuduv väli --

    def test_sli5_detects_missing_field(self) -> None:
        """SLI-5: kui kohustuslik auditiväli puudub, peab suhtarv langema."""
        from domain.report.ops import compute_sli5_audit_completeness
        incomplete_report = {
            "run": {
                "sv_schema_version": "1.0.0",
                "mapping_version": "1.0.0",
                # ruleset_version puudub
                "adapter_version": "0.1.0",
            }
        }
        result = compute_sli5_audit_completeness(incomplete_report)
        assert result["sli5_audit_completeness_ratio"] < 1.0
        assert result["required_fields_present"] == 3
        assert result["required_fields_total"] == 4

    # -- None väärtus --

    def test_sli5_none_value_is_not_substantive(self) -> None:
        """SLI-5: kui kohustuslik auditiväli on None, ei ole see sisuline olemasolu."""
        from domain.report.ops import compute_sli5_audit_completeness
        report_with_none = {
            "run": {
                "sv_schema_version": "1.0.0",
                "mapping_version": "1.0.0",
                "ruleset_version": None,
                "adapter_version": "0.1.0",
            }
        }
        result = compute_sli5_audit_completeness(report_with_none)
        assert result["sli5_audit_completeness_ratio"] < 1.0
        assert result["required_fields_present"] == 3

    # -- Tühi string --

    def test_sli5_empty_string_is_not_substantive(self) -> None:
        """SLI-5: kui kohustuslik auditiväli on tühi string, ei ole see sisuline olemasolu."""
        from domain.report.ops import compute_sli5_audit_completeness
        report_with_empty = {
            "run": {
                "sv_schema_version": "1.0.0",
                "mapping_version": "",
                "ruleset_version": "1.1.0",
                "adapter_version": "0.1.0",
            }
        }
        result = compute_sli5_audit_completeness(report_with_empty)
        assert result["sli5_audit_completeness_ratio"] < 1.0
        assert result["required_fields_present"] == 3

    # -- Tühikutest koosnev string --

    def test_sli5_whitespace_only_is_not_substantive(self) -> None:
        """SLI-5: kui kohustuslik auditiväli on ainult tühikud, ei ole see sisuline olemasolu."""
        from domain.report.ops import compute_sli5_audit_completeness
        report_with_whitespace = {
            "run": {
                "sv_schema_version": "1.0.0",
                "mapping_version": "   ",
                "ruleset_version": "1.1.0",
                "adapter_version": "0.1.0",
            }
        }
        result = compute_sli5_audit_completeness(report_with_whitespace)
        assert result["sli5_audit_completeness_ratio"] < 1.0
        assert result["required_fields_present"] == 3

    # -- Üksikud auditiväljad --

    def test_sli5_sv_schema_version(self, report: dict) -> None:
        """SLI-5: report.run peab kandma sv_schema_version välja."""
        assert "sv_schema_version" in report["run"]
        assert report["run"]["sv_schema_version"] != ""

    def test_sli5_mapping_version(self, report: dict) -> None:
        """SLI-5: report.run peab kandma mapping_version välja."""
        assert "mapping_version" in report["run"]
        assert report["run"]["mapping_version"] != ""

    def test_sli5_ruleset_version(self, report: dict) -> None:
        """SLI-5: report.run peab kandma ruleset_version välja."""
        assert "ruleset_version" in report["run"]
        assert report["run"]["ruleset_version"] != ""

    def test_sli5_adapter_version(self, report: dict) -> None:
        """SLI-5: report.run peab kandma adapter_version välja."""
        assert "adapter_version" in report["run"]
        assert report["run"]["adapter_version"] != ""


# ---------------------------------------------------------------------------
# SLI-6: Referentsjõudlus
# ---------------------------------------------------------------------------
#
# SLI-6 = mediaanne töötlusaeg referentsandmestikul
#
# SLI-6 ei ole lihtsalt "väikese testandmestiku töötlusaeg".
# SLI-6 on näitaja, mida hinnatakse eraldi jõudlusmõõtmise alusel
# kokkulepitud referentsandmestikul (D9, ~1000 tehingut).
#
# Mõõtmismetoodika:
#   1) 1 proovijooks, mille tulemust ei arvestata
#   2) 5 mõõdetud jooksu
#   3) tulemuseks on nende 5 mõõdetud jooksu mediaan
#
# SLI-6 ei kuulu report.json metrics sektsiooni, sest see on eraldi
# mõõtmise tulemus, mitte ühe jooksu artefakt.
# ---------------------------------------------------------------------------

# SLI-6 on informatiivne referentsmõõtmine regressioonide jälgimiseks.
#
# Jäika universaalset lävendit ei seata, sest:
# - in-memory fake portidega mediaan on ~3–8 ms,
# - FS-adapteritega mediaan on ~300–500 ms,
# - erinevus sõltub I/O kihist, mitte pipeline'i domeeniloogikast.
#
# Kui soovitakse regressioonilävendit, tuleks see kalibreerida konkreetse
# keskkonna ja I/O kihi alusel. Näiteks FS-adapteritega mõistlik lävend
# oleks ~1000 ms (2× mõõdetud mediaanist 300–500 ms).
_SLI6_THRESHOLD_MS: float | None = 500.0


def run_sli6_benchmark(
    booked: list[dict],
    pending: list[dict] | None = None,
    *,
    proovijooksud: int = 1,
    measured_runs: int = 5,
) -> dict[str, float | int]:
    """SLI-6 referentsjõudluse mõõtmine.

    Käivitab pipeline proovijooksude + mõõdetud jooksude arvu korda
    ja tagastab mõõdetud jooksude mediaani.

    Returns
    -------
    dict with keys:
        median_ms : float  — 5 mõõdetud jooksu mediaan millisekundites
        all_times_ms : list[float]  — kõik mõõdetud ajad
        proovijooksu_ms : float  — proovijooksu aeg
    """
    import statistics

    pending = pending or []

    # Proovijooksud
    proovijooksu_ajad: list[float] = []
    for _ in range(proovijooksud):
        t0 = time.perf_counter()
        _run(booked=booked, pending=pending)
        proovijooksu_ajad.append((time.perf_counter() - t0) * 1000)

    # Mõõdetud jooksud
    measured_times: list[float] = []
    for _ in range(measured_runs):
        t0 = time.perf_counter()
        _run(booked=booked, pending=pending)
        measured_times.append((time.perf_counter() - t0) * 1000)

    median_ms = statistics.median(measured_times)

    return {
        "median_ms": round(median_ms, 2),
        "all_times_ms": [round(t, 2) for t in measured_times],
        "proovijooksu_ms": round(proovijooksu_ajad[0], 2) if proovijooksu_ajad else 0.0,
    }


class TestSLI6ReferencePerformance:
    """SLI-6 — referentsjõudlus: mediaanne töötlusaeg referentsandmestikul.

    Kasutab ~1000 tehinguga sünteetilist andmestikku (D9 formaadis).
    Mõõtmismetoodika: 1 proovijooks + 5 mõõdetud jooksu; tulemus on mediaan.

    SLI-6 ei ole report.json metrics väli, vaid eraldi mõõtmise tulemus.
    """

    @pytest.fixture(scope="class")
    def reference_dataset(self) -> tuple[list[dict], list[dict]]:
        """Genereerib ~1000 tehinguga referentsandmestiku (D9 formaadis)."""
        booked = [
            _tx(
                transaction_id=f"REF-B{i:04d}",
                amount=f"{10 + (i % 500)}.{i % 100:02d}",
                value_date=f"2025-{1 + (i % 12):02d}-{1 + (i % 28):02d}",
                booking_date=f"2025-{1 + (i % 12):02d}-{1 + (i % 28):02d}",
                debtor_name=f"Sender_{i % 50}",
            )
            for i in range(800)
        ]
        pending = [
            _tx(
                transaction_id=f"REF-P{i:04d}",
                amount=f"{5 + (i % 200)}.{i % 100:02d}",
                value_date=f"2025-{1 + (i % 12):02d}-{1 + (i % 28):02d}",
                booking_date=None,
                debtor_name=f"PendSender_{i % 30}",
            )
            for i in range(200)
        ]
        return booked, pending

    @pytest.fixture(scope="class")
    def benchmark_result(
        self, reference_dataset: tuple[list[dict], list[dict]],
    ) -> dict:
        booked, pending = reference_dataset
        return run_sli6_benchmark(booked, pending, proovijooksud=1, measured_runs=5)

    def test_sli6_reference_benchmark(self, benchmark_result: dict) -> None:
        """SLI-6: mõõdab referentsjõudlust 1000 tehinguga andmestikul.

        Metoodika: 1 proovijooks + 5 mõõdetud jooksu; tulemus on mediaan.

        See on informatiivne referentsmõõtmine regressioonide jälgimiseks.
        Jäika lävendit ei jõustata vaikimisi, sest mõõdetud mediaan sõltub
        I/O kihist (in-memory ~5 ms vs FS ~400 ms). Kui _SLI6_THRESHOLD_MS
        on seadistatud, kontrollitakse seda.
        """
        median = benchmark_result["median_ms"]
        print(f"\nSLI-6 referentsjõudlus (informatiivne):")
        print(f"  Mediaan:        {median:.2f} ms")
        print(f"  Mõõdetud ajad:  {benchmark_result['all_times_ms']} ms")
        print(f"  Proovijooks:    {benchmark_result['proovijooksu_ms']:.2f} ms")

        if _SLI6_THRESHOLD_MS is not None:
            assert median <= _SLI6_THRESHOLD_MS, (
                f"SLI-6 mediaan {median:.2f} ms ületab lävendi {_SLI6_THRESHOLD_MS} ms"
            )

    def test_sli6_median_is_positive(self, benchmark_result: dict) -> None:
        """Mediaan peab olema positiivne arv."""
        assert benchmark_result["median_ms"] > 0

    def test_sli6_five_measured_runs(self, benchmark_result: dict) -> None:
        """Mõõtmistulemus peab sisaldama täpselt 5 mõõdetud aega."""
        assert len(benchmark_result["all_times_ms"]) == 5
