"""SLI/SLO testid adapteri pipeline'ile.

Iga testiklass vastab ühele teenustaseme indikaatorile (SLI) ja kontrollib,
kas pipeline täidab vastava teenustaseme eesmärgi (SLO).

SLI definitsioonid ja SLO sihtmärgid
--------------------------------------
SLI-1  SV skeemi/lepingu      Relevantsete SV tehinguväljade osakaal, millele C-01 määrab
       katvus                 üheselt kaardistus- või tuletamisloogika
                              SLO: ≥ 0.95

SLI-2  Valideerimise läbivus  Valideeritud kirjete osakaal sisendi suhtes (pass-through)
                              SLO: ≥ 0.99 puhaste/tootmislaadsete datasettide korral;
                              vea-/äärejuhtumite datasettidel raporteeritakse kirjeldava metrikana

QC2    Langetuste raporteerimine  Kõik langetused kajastatakse dropped_details[] all (operational control)
                              SLO: 100 % langetustest ilmub report.dropped_details[] all

SLI-3  Invariantide täituvus  Invariantide vastavuse suhtarv (invariant compliance ratio)
                              = invariant_correct_total / invariant_checked_total
                              SLO: ≥ 0.999 puhaste/tootmislaadsete datasettide korral;
                              critical_invariant_violations_total == 0

Gate   Operatiivne            Vea-drop lävend (ei ole SLI)
       kvaliteedivärav        SLO: error_drop_ratio < 5 % → PARTIAL_SUCCESS; ≥ 5 % → FAIL

SLI-4  Determinism            Identne sisend annab baidilt identse väljundi
                              SLO: 100 % korduvjooksudest sama kellaga toodab identsed sõnastikud

SLI-5  Spetsifikatsioonide    Iga jooks kannab kõiki versiooni metaandmeid
       versioonid             SLO: 100 % jooksudest sisaldab sv_schema_version, mapping_version,
                              ruleset_version, adapter_version väljades report.run

SLI-6  Jõudlus               Pipeline lõpetab ajaeelarve piires väikeste datasettide korral
                              SLO: ≤ 500 ms datasetile, kus on ≤ 10 tehingut
"""

from __future__ import annotations

import time

import pytest

from application.pipeline import run_pipeline
from tests.fakes import FakeDatasetPort, FakeOutputPort, FakeSpecPort, FixedClock


# ---------------------------------------------------------------------------
# Jagatud abifunktsioonid
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


def _report(iban: str = "DE89370400440532013000", booked: list | None = None, pending: list | None = None) -> dict:
    return {
        "account": {"iban": iban},
        "transactions": {
            "booked": booked or [],
            "pending": pending or [],
        },
    }


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
        dataset_id="sli-slo-test",
        input_dir="<memory>",
    )
    return summary, out


# ---------------------------------------------------------------------------
# SLI-1: SV skeemi/lepingu katvus (schema/contract coverage)
# SLO: ≥ 0.95 — C-01 peab katma vähemalt 95 % relevantsetest SV tehinguväljadest
# ---------------------------------------------------------------------------

class TestSLI1SchemaContractCoverage:
    """SLI-1 — SV skeemi/lepingu katvus.

    SLI-1 = covered_relevant_sv_fields / relevant_sv_fields_total

    See on staatiline spetsifikatsioonitaseme mõõdik, mis põhineb
    hooldataval katvusdeklaratsioonil (SLI1_FIELD_COVERAGE moodulis
    domain.report.ops). Mõõdik ei sõltu konkreetsest andmestikust ega jooksust.
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
        assert "schema_coverage_ratio" in sli1
        assert "relevant_sv_fields_total" in sli1
        assert "covered_relevant_sv_fields" in sli1

    def test_sli1_relevant_fields_positive(self) -> None:
        """relevant_sv_fields_total peab olema > 0."""
        _, out = _run(booked=[_tx()])
        assert out.report["metrics"]["sli1"]["relevant_sv_fields_total"] > 0

    def test_sli1_covered_leq_total(self) -> None:
        """covered_relevant_sv_fields <= relevant_sv_fields_total."""
        _, out = _run(booked=[_tx()])
        sli1 = out.report["metrics"]["sli1"]
        assert sli1["covered_relevant_sv_fields"] <= sli1["relevant_sv_fields_total"]

    def test_sli1_ratio_in_unit_interval(self) -> None:
        """schema_coverage_ratio peab olema vahemikus [0, 1]."""
        _, out = _run(booked=[_tx()])
        ratio = out.report["metrics"]["sli1"]["schema_coverage_ratio"]
        assert 0.0 <= ratio <= 1.0

    def test_sli1_baseline_meets_slo(self) -> None:
        """Praeguse baasprofiiliga SLI-1 peab olema >= 0.95 (SLO)."""
        _, out = _run(booked=[_tx()])
        ratio = out.report["metrics"]["sli1"]["schema_coverage_ratio"]
        assert ratio >= 0.95

    def test_sli1_ratio_decreases_when_field_uncovered(self) -> None:
        """Kui üks väli märgitakse katvamata, peab SLI-1 suhtarv langema."""
        from domain.report.ops import SLI1_FIELD_COVERAGE, compute_sli1_coverage

        baseline = compute_sli1_coverage()
        # Ülekirjutus: üks väli märgitakse katvamata
        override = dict(SLI1_FIELD_COVERAGE)
        override["record_id"] = False
        reduced = compute_sli1_coverage(coverage_map=override)

        assert reduced["schema_coverage_ratio"] < baseline["schema_coverage_ratio"]
        assert reduced["covered_relevant_sv_fields"] == baseline["covered_relevant_sv_fields"] - 1
        assert reduced["relevant_sv_fields_total"] == baseline["relevant_sv_fields_total"]

    def test_sli1_in_pipeline_summary(self) -> None:
        """SLI-1 peab olema ka pipeline'i tagastatud summary.metrics all."""
        summary, _ = _run(booked=[_tx()])
        assert "sli1" in summary["metrics"]
        assert summary["metrics"]["sli1"]["schema_coverage_ratio"] >= 0.95


# ---------------------------------------------------------------------------
# Struktuurne väljundi terviklikkus (varem SLI-1 struktuurikontrollid)
# ---------------------------------------------------------------------------
# Need testid kontrollivad, et väljundartefaktid (SV, ML, LLM, raport)
# sisaldavad nõutud tipptaseme struktuuri ja võtmeid.  Need on kasulikud
# struktuurse terviklikkuse kontrollid, kuid EI OLE ametlik SLI-1 metrika.
# SLI-1 on skeemi/lepingu katvus (vt TestSLI1SchemaContractCoverage).
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
        assert isinstance(out.report["dropped_details"], list)


# ---------------------------------------------------------------------------
# SLI-2: Valideerimise läbivus (validation pass-through ratio)
# SLO: ≥ 0.99 puhaste datasettide korral; vea-datasettidel kirjeldav metrika
# ---------------------------------------------------------------------------

class TestSLI2ValidationPassThrough:
    """SLI-2 — valideeritud kirjete osakaal sisendi suhtes.

    SLI-2 = passed_validation_total / input_records_total
    where:
      input_records_total    = transactions_total  (all raw input tx)
      passed_validation_total = transactions_emitted_sv (survived mapping + validation + dedup)
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
# QC2: Langetuste raporteerimine (operational drop-reporting coverage)
# SLO: 100 % langetustest ilmub report.dropped_details[] all
# ---------------------------------------------------------------------------

class TestQC2DropReporting:
    """QC2 — kõik langetused kajastatakse dropped_details[] all (operational control).

    This was previously labeled SLI-2. Renamed to QC2 to restore the original
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
        """Puhas sisend → QC2 all_drops_reported == True, ratio == 1.0."""
        summary, _ = _run(booked=[_tx()])
        qc2 = summary["metrics"]["qc2"]
        assert qc2["all_drops_reported"] is True
        assert qc2["drop_reporting_ratio"] == 1.0

    def test_qc2_all_drops_reported_with_drops(self) -> None:
        """Langetustega sisend → QC2 all_drops_reported == True (kõik kajastatud)."""
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
# SLO: Kaks identset jooksu sama fikseeritud kellaga toodavad identsed väljundid
# ---------------------------------------------------------------------------

class TestSLI4Determinism:
    """SLI-4 — korduvjooksud sama sisendi ja kellaga toodavad identse väljundi."""

    @pytest.fixture(scope="class")
    def two_runs(self) -> tuple[FakeOutputPort, FakeOutputPort]:
        clock = FixedClock(fixed_utc="2026-03-01T12:00:00Z", fixed_run_id="det-run-42")
        booked = [
            _tx(amount="100.00", transaction_id="TX1"),
            _tx(amount="200.00", transaction_id="TX2", debtor_name=None, creditor_name="Shop"),
        ]
        _, out1 = _run(booked=booked, clock=clock)
        _, out2 = _run(booked=booked, clock=clock)
        return out1, out2

    def test_sv_is_identical(self, two_runs: tuple[FakeOutputPort, FakeOutputPort]) -> None:
        """SV bundle peab olema identne kahe sama sisendiga jooksu vahel."""
        out1, out2 = two_runs
        assert out1.sv == out2.sv

    def test_ml_is_identical(self, two_runs: tuple[FakeOutputPort, FakeOutputPort]) -> None:
        """ML read peavad olema identsed kahe sama sisendiga jooksu vahel."""
        out1, out2 = two_runs
        assert out1.ml == out2.ml

    def test_llm_is_identical(self, two_runs: tuple[FakeOutputPort, FakeOutputPort]) -> None:
        """LLM kontekst peab olema identne kahe sama sisendiga jooksu vahel."""
        out1, out2 = two_runs
        assert out1.llm == out2.llm

    def test_report_is_identical(self, two_runs: tuple[FakeOutputPort, FakeOutputPort]) -> None:
        """Raport peab olema identne kahe sama sisendiga jooksu vahel."""
        out1, out2 = two_runs
        assert out1.report == out2.report

    def test_run_id_is_fixed(self, two_runs: tuple[FakeOutputPort, FakeOutputPort]) -> None:
        """run_id peab tulema kellalt, mitte juhuslikust generaatorist."""
        out1, out2 = two_runs
        assert out1.run_id == out2.run_id == "det-run-42"

    def test_created_at_is_fixed(self, two_runs: tuple[FakeOutputPort, FakeOutputPort]) -> None:
        """created_at_utc peab tulema kellalt, mitte süsteemiajalt."""
        out1, out2 = two_runs
        assert out1.created_at_utc == out2.created_at_utc == "2026-03-01T12:00:00Z"


# ---------------------------------------------------------------------------
# SLI-5: Spetsifikatsioonide versioonid
# SLO: 100 % jooksudest kannab kõiki 4 versioonivälja report.run all
# ---------------------------------------------------------------------------

class TestSLI5SpecVersioning:
    """SLI-5 — iga jooks emiteerib kõik nõutud versiooni metaandmete väljad."""

    @pytest.fixture(scope="class")
    def report(self) -> dict:
        _, out = _run(booked=[_tx()])
        assert out.report is not None
        return out.report

    def test_report_run_has_sv_schema_version(self, report: dict) -> None:
        """report.run peab kandma sv_schema_version välja."""
        assert "sv_schema_version" in report["run"]
        assert report["run"]["sv_schema_version"] != ""

    def test_report_run_has_mapping_version(self, report: dict) -> None:
        """report.run peab kandma mapping_version välja."""
        assert "mapping_version" in report["run"]
        assert report["run"]["mapping_version"] != ""

    def test_report_run_has_ruleset_version(self, report: dict) -> None:
        """report.run peab kandma ruleset_version välja."""
        assert "ruleset_version" in report["run"]
        assert report["run"]["ruleset_version"] != ""

    def test_report_run_has_adapter_version(self, report: dict) -> None:
        """report.run peab kandma adapter_version välja."""
        assert "adapter_version" in report["run"]
        assert report["run"]["adapter_version"] != ""

    def test_report_run_has_run_id(self, report: dict) -> None:
        """report.run peab kandma run_id välja."""
        assert "run_id" in report["run"]
        assert report["run"]["run_id"] != ""

    def test_report_run_has_created_at_utc(self, report: dict) -> None:
        """report.run peab kandma created_at_utc ajatemplit."""
        assert "created_at_utc" in report["run"]
        assert report["run"]["created_at_utc"] != ""

    def test_report_has_schema_version_field(self, report: dict) -> None:
        """Raport ise peab kandma report_schema_version välja juuretasemel."""
        assert "report_schema_version" in report
        assert report["report_schema_version"] != ""


# ---------------------------------------------------------------------------
# SLI-6: Jõudlus
# SLO: Pipeline lõpetab ≤ 500 ms, kui datasett sisaldab ≤ 10 tehingut
# ---------------------------------------------------------------------------

_PERFORMANCE_SLO_MS = 500  # millisekundit


class TestSLI6Performance:
    """SLI-6 — pipeline peab lõpetama 500 ms jooksul väikeste datasettide korral."""

    def test_single_transaction_within_slo(self) -> None:
        """Pipeline 1 tehinguga peab lõpetama ≤ 500 ms."""
        t0 = time.perf_counter()
        _run(booked=[_tx()])
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms <= _PERFORMANCE_SLO_MS, (
            f"Pipeline took {elapsed_ms:.1f} ms — exceeds SLO of {_PERFORMANCE_SLO_MS} ms"
        )

    def test_ten_transactions_within_slo(self) -> None:
        """Pipeline 10 tehinguga peab lõpetama ≤ 500 ms."""
        txns = [_tx(transaction_id=f"T{i}", amount=str(10 + i)) for i in range(10)]
        t0 = time.perf_counter()
        _run(booked=txns)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms <= _PERFORMANCE_SLO_MS, (
            f"Pipeline took {elapsed_ms:.1f} ms — exceeds SLO of {_PERFORMANCE_SLO_MS} ms"
        )

    def test_mixed_booked_and_pending_within_slo(self) -> None:
        """Pipeline 5 booked + 5 pending tehinguga peab lõpetama ≤ 500 ms."""
        booked = [_tx(transaction_id=f"B{i}", amount=str(10 + i)) for i in range(5)]
        pending = [_tx(transaction_id=f"P{i}", amount=str(50 + i), booking_date=None) for i in range(5)]
        t0 = time.perf_counter()
        _run(booked=booked, pending=pending)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms <= _PERFORMANCE_SLO_MS, (
            f"Pipeline took {elapsed_ms:.1f} ms — exceeds SLO of {_PERFORMANCE_SLO_MS} ms"
        )
