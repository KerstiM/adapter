"""
Happy-path tests for the adapter pipeline.

Tests verify the full RAW -> SV -> ML/LLM projection flow
using datasets/D1_synth_valid_small Berlin AIS fixtures against specs:
  S-01 (flat transactions, amount object, IN/OUT direction)
  C-02 (BOOKED+PENDING, row_id as int)
  C-03 (LLM context with short field names)

Output structure per run:
  out/<timestamp>_<run_id>/
      sv.json
      report.json
      projections/ml_v1.csv
      projections/llm_context_v1.json
"""
import csv
import json
import statistics
import time
from pathlib import Path

import jsonschema
import pytest

from entrypoints.wiring_fs import run_pipeline_fs

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = PROJECT_ROOT / "spec"
DATASETS_DIR = PROJECT_ROOT / "datasets"
DATA_D1 = DATASETS_DIR / "D1_synth_valid_small"

FIXED_RUN_ID = "test-run-001"
FIXED_TS = "2026-01-01T00:00:00Z"


def _load_schema(name: str) -> dict:
    with open(SPEC_DIR / "schemas" / name, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Fixture: run pipeline once per test class
# ---------------------------------------------------------------------------

@pytest.fixture()
def d1_output(tmp_path: Path) -> tuple[dict, Path]:
    """Run pipeline on D1 and return (summary, run_folder)."""
    summary = run_pipeline_fs(
        data_dir=DATA_D1,
        output_dir=tmp_path,
        spec_dir=SPEC_DIR,
        run_id=FIXED_RUN_ID,
        created_at_utc=FIXED_TS,
    )
    run_folder = Path(summary["run_folder"])
    return summary, run_folder


# ---------------------------------------------------------------------------
# Acceptance checks (A-D)
# ---------------------------------------------------------------------------

class TestAcceptanceChecks:
    """Acceptance checks from the task specification."""

    def test_A_run_id_consistent(self, d1_output: tuple) -> None:
        """A) sv.meta.run_id == report.run.run_id == llm.meta.run_id"""
        _, run_folder = d1_output

        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            llm = json.load(f)

        sv_run_id = sv["meta"]["run_id"]
        report_run_id = report["run"]["run_id"]
        llm_run_id = llm["meta"]["run_id"]

        assert sv_run_id == report_run_id == llm_run_id == FIXED_RUN_ID

    def test_B_emitted_count_matches_sv(self, d1_output: tuple) -> None:
        """B) report.summary.counts.transactions_emitted_sv == len(sv.transactions)"""
        _, run_folder = d1_output

        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        emitted = report["summary"]["counts"]["transactions_emitted_sv"]
        assert emitted == len(sv["transactions"])

    def test_C_inv05_warn_in_report(self, d1_output: tuple) -> None:
        """C) If any sv.transactions[*].flags contains INV-05, report.by_severity.WARN >= 1"""
        _, run_folder = d1_output

        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        has_inv05 = any(
            flag["id"].startswith("INV-05")
            for tx in sv["transactions"]
            for flag in tx.get("flags", [])
        )
        if has_inv05:
            assert report["summary"]["by_severity"]["WARN"] >= 1
            ci_stage = next(s for s in report["summary"]["by_stage"] if s["stage"] == "CHECK_INVARIANTS")
            assert ci_stage["warnings"] >= 1

    def test_D_d1_counts(self, d1_output: tuple) -> None:
        """D) D1: accounts_total=1, transactions_total=7, dropped=0.
        Note: D1 has 5 booked + 2 pending = 7 raw (no standing_orders.json).
        All transactions have valueDate -> emitted=7, dropped=0.
        Invariant: total == emitted + dropped.
        """
        summary, _ = d1_output
        counts = summary["counts"]
        assert counts["accounts_total"] == 1
        assert counts["transactions_total"] == 7
        assert counts["transactions_dropped"] == 0
        assert counts["transactions_emitted_sv"] == 7
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]


# ---------------------------------------------------------------------------
# Happy-path: full pipeline on D1
# ---------------------------------------------------------------------------

class TestHappyPathPipeline:
    """End-to-end happy-path tests using D1 fixtures."""

    def test_outcome_not_fail(self, d1_output: tuple) -> None:
        summary, _ = d1_output
        assert summary["outcome"] in ("SUCCESS", "PARTIAL_SUCCESS")

    def test_transaction_counts(self, d1_output: tuple) -> None:
        summary, _ = d1_output
        counts = summary["counts"]
        assert counts["transactions_total"] == 7
        assert counts["accounts_total"] == 1
        assert counts["transactions_emitted_sv"] == 7

    def test_download_only_not_present(self, d1_output: tuple) -> None:
        """D1 has no transactions_download.json -> no RUN_DOWNLOAD_ONLY flag."""
        summary, _ = d1_output
        download_flags = [f for f in summary["run_flags"] if f["id"] == "RUN_DOWNLOAD_ONLY"]
        assert len(download_flags) == 0

    # --- Run folder structure ---

    def test_run_folder_structure(self, d1_output: tuple) -> None:
        """All expected output files exist in the run folder."""
        _, run_folder = d1_output
        assert (run_folder / "sv.json").exists()
        assert (run_folder / "report.json").exists()
        assert (run_folder / "projections" / "ml_v1.csv").exists()
        assert (run_folder / "projections" / "llm_context_v1.json").exists()

    def test_run_folder_name_contains_run_id(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        assert FIXED_RUN_ID in run_folder.name

    # --- SV Bundle tests ---

    def test_sv_validates_against_schema(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        schema = _load_schema("S-01_sv_schema.json")
        jsonschema.validate(sv, schema)

    def test_sv_meta(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        meta = sv["meta"]
        assert meta["run_id"] == FIXED_RUN_ID
        assert meta["created_at_utc"] == FIXED_TS
        assert meta["profile_id"] == "default"
        assert meta["spec_versions"]["S-01"] == "1.0.0"
        assert meta["spec_versions"]["C-01"] == "1.0.0"

    def test_sv_accounts_structure(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        assert len(sv["accounts"]) == 1
        acct = sv["accounts"][0]
        assert acct["iban"] == "DE14177763170669074391"
        assert acct["currency"] == "EUR"
        assert acct["name"] == "D1 Smoke Test Account"

    def test_sv_transactions_flat_array(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        assert isinstance(sv["transactions"], list)
        assert len(sv["transactions"]) == 7

    def test_sv_transaction_required_fields(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["transactions"]:
            assert tx["record_id"]
            assert tx["account_id"]
            assert tx["status"] in ("BOOKED", "PENDING", "INFORMATION")
            assert tx["value_date"]
            assert tx["direction"] in ("IN", "OUT")
            assert isinstance(tx["amount"], dict)
            assert tx["amount"]["currency"]
            assert tx["amount"]["raw"]
            assert tx["amount"]["signed"]
            assert tx["amount"]["abs"]
            assert isinstance(tx["counterparty"], dict)
            assert tx["counterparty"]["role"] in ("CREDITOR", "DEBTOR", "UNKNOWN")
            assert isinstance(tx["flags"], list)
            assert isinstance(tx["source"], dict)

    def test_sv_direction_inference(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        by_remittance = {}
        for tx in sv["transactions"]:
            if tx.get("remittance"):
                by_remittance[tx["remittance"]] = tx

        # "Invoice L4WUXGIA" has creditorName (Henrik Berg) -> OUT
        assert by_remittance["Invoice L4WUXGIA"]["direction"] == "OUT"
        assert by_remittance["Invoice L4WUXGIA"]["counterparty"]["role"] == "CREDITOR"

        # "Donation to charity" has debtorName (Luca Tamm) -> IN
        assert by_remittance["Donation to charity"]["direction"] == "IN"
        assert by_remittance["Donation to charity"]["counterparty"]["role"] == "DEBTOR"

    def test_sv_amount_object_structure(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        by_remittance = {}
        for tx in sv["transactions"]:
            if tx.get("remittance"):
                by_remittance[tx["remittance"]] = tx

        # Invoice L4WUXGIA: OUT, raw=-2842.31, signed should be negative
        ex1 = by_remittance["Invoice L4WUXGIA"]["amount"]
        assert ex1["raw"] == "-2842.31"
        assert ex1["signed"] == "-2842.31"
        assert ex1["abs"] == "2842.31"
        assert ex1["currency"] == "EUR"

        # Rent payment June: IN (debtorName Markus Tamm), raw=255.43, signed should be positive
        ex2 = by_remittance["Rent payment June"]["amount"]
        assert ex2["raw"] == "255.43"
        assert ex2["signed"] == "255.43"
        assert ex2["abs"] == "255.43"

    def test_sv_amount_sign_matches_direction(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["transactions"]:
            signed = float(tx["amount"]["signed"])
            if tx["direction"] == "OUT":
                assert signed <= 0, f"OUT amount should be negative: {tx['amount']}"
            elif tx["direction"] == "IN":
                assert signed >= 0, f"IN amount should be positive: {tx['amount']}"

    def test_sv_no_inv05_in_d1(self, d1_output: tuple) -> None:
        """D1 has no sign-direction mismatches -> no INV-05 flags."""
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        inv05_count = sum(
            1 for tx in sv["transactions"]
            for f in tx.get("flags", [])
            if f["id"].startswith("INV-05")
        )
        assert inv05_count == 0

    def test_sv_source_lineage(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["transactions"]:
            assert tx["source"]["input_file"]
            assert tx["source"]["input_path"].startswith("$.transactions.")

    def test_sv_no_information_in_d1(self, d1_output: tuple) -> None:
        """D1 has no standing_orders.json -> no INFORMATION transactions in SV."""
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        info_txs = [t for t in sv["transactions"] if t["status"] == "INFORMATION"]
        assert len(info_txs) == 0

    # --- Report tests ---

    def test_report_structure(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        assert "run" in report
        assert "summary" in report
        assert report["run"]["run_id"] == FIXED_RUN_ID
        assert report["run"]["created_at_utc"] == FIXED_TS
        assert "counts" in report["summary"]
        assert "by_severity" in report["summary"]
        assert "by_stage" in report["summary"]

    def test_report_by_stage_keys(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        expected_stages = {
            "READ_INPUT", "STANDARDIZE_TO_SV", "VALIDATE_SCHEMA",
            "CHECK_INVARIANTS", "PROJECT_ML", "PROJECT_LLM",
        }
        actual_stages = {s["stage"] for s in report["summary"]["by_stage"]}
        assert expected_stages.issubset(actual_stages)

    def test_report_by_severity_critical_zero(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        assert report["summary"]["by_severity"]["CRITICAL"] == 0

    def test_report_by_severity_issues_matches_issues_array(self, d1_output: tuple) -> None:
        """by_severity_issues peab kattuma issues[] tõsiduse jaotusega — üks
        inimloetav indikaator, mis vastab CLI-s prinditavale `issues:` loendile.
        """
        _, run_folder = d1_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        issues = report["issues"]
        bsi = report["summary"]["by_severity_issues"]
        for sev in ("CRITICAL", "ERROR", "WARN", "INFO"):
            expected = sum(1 for i in issues if i.get("severity") == sev)
            assert bsi[sev] == expected
        assert sum(bsi.values()) == len(issues)

    # --- ML projection tests ---

    def test_ml_csv_exists(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        assert (run_folder / "projections" / "ml_v1.csv").exists()

    def test_ml_csv_validates_against_schema(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        schema = _load_schema("S-02_ml_projection_schema.json")
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for raw_row in rows:
            row: dict = {**raw_row}
            row["row_id"] = int(row["row_id"])
            for field in ("booking_date", "counterparty_name", "remittance"):
                if row.get(field) == "":
                    row[field] = None
            jsonschema.validate(row, schema)

    def test_ml_csv_correct_columns(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected = {
                "row_id", "account_id", "record_id", "status",
                "booking_date", "value_date", "direction", "currency",
                "signed_amount", "abs_amount", "counterparty_name", "remittance",
            }
            assert set(reader.fieldnames) == expected

    def test_ml_csv_booked_and_pending(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        statuses = {r["status"] for r in rows}
        assert "BOOKED" in statuses
        assert "PENDING" in statuses
        assert len(rows) == 7

    def test_ml_csv_row_id_is_sequential(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        row_ids = [int(r["row_id"]) for r in rows]
        assert row_ids == list(range(1, len(rows) + 1))

    def test_ml_csv_sorted_deterministically(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        sort_keys = [(r["account_id"], r["value_date"], r["record_id"]) for r in rows]
        assert sort_keys == sorted(sort_keys)

    # --- LLM context tests ---

    def test_llm_context_exists(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        assert (run_folder / "projections" / "llm_context_v1.json").exists()

    def test_llm_context_validates_against_schema(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        schema = _load_schema("S-03_llm_context_schema.json")
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        jsonschema.validate(ctx, schema)

    def test_llm_context_meta(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)

        assert ctx["meta"]["run_id"] == FIXED_RUN_ID
        assert ctx["meta"]["created_at_utc"] == FIXED_TS
        assert ctx["meta"]["iban"] == "DE14177763170669074391"
        assert ctx["meta"]["currency"] == "EUR"

    def test_llm_context_tx_fields(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)

        for tx in ctx["tx"]:
            assert "id" in tx
            assert "d" in tx
            assert "s" in tx
            assert "dir" in tx
            assert "a" in tx
            assert "c" in tx

    def test_llm_context_booked_and_pending(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        statuses = {tx["s"] for tx in ctx["tx"]}
        assert "BOOKED" in statuses
        assert "PENDING" in statuses
        assert len(ctx["tx"]) == 7

    def test_schema_validation_no_issues(self, d1_output: tuple) -> None:
        """D1 has no standing_orders.json -> no schema validation issues."""
        summary, _ = d1_output
        schema_issues = [i for i in summary["issues"] if "validation" in i.get("message", "").lower()]
        assert len(schema_issues) == 0


# ---------------------------------------------------------------------------
# Extra projections: FS end-to-end tests with extensions_eval profile
# ---------------------------------------------------------------------------

@pytest.fixture()
def d1_extensions_output(tmp_path: Path) -> tuple[dict, Path]:
    """Run pipeline on D1 with extensions_eval profile."""
    summary = run_pipeline_fs(
        data_dir=DATA_D1,
        output_dir=tmp_path,
        spec_dir=SPEC_DIR,
        profile_id="extensions_eval",
        run_id=FIXED_RUN_ID,
        created_at_utc=FIXED_TS,
    )
    run_folder = Path(summary["run_folder"])
    return summary, run_folder


class TestExtraProjectionsFS:
    """FS end-to-end testid extensions_eval profiiliga.

    Tõestab, et extra projections mehhanism töötab päris
    failisüsteemi adapteritega, mitte ainult FakeSpecPort'iga.
    """

    def test_stats_file_exists(self, d1_extensions_output: tuple) -> None:
        """extensions_eval profiiliga tekib projections/stats_v1.json."""
        _, run_folder = d1_extensions_output
        assert (run_folder / "projections" / "stats_v1.json").exists()

    def test_monthly_balance_file_exists(self, d1_extensions_output: tuple) -> None:
        """extensions_eval profiiliga tekib projections/monthly_balance_v1.json."""
        _, run_folder = d1_extensions_output
        assert (run_folder / "projections" / "monthly_balance_v1.json").exists()

    def test_stats_validates_against_s06(self, d1_extensions_output: tuple) -> None:
        """stats_v1.json valideerub tõelise S-06 skeemi vastu."""
        _, run_folder = d1_extensions_output
        schema = _load_schema("S-06_stats_schema.json")
        with open(run_folder / "projections" / "stats_v1.json", encoding="utf-8") as f:
            data = json.load(f)
        jsonschema.validate(data, schema)

    def test_monthly_balance_validates_against_s07(self, d1_extensions_output: tuple) -> None:
        """monthly_balance_v1.json valideerub tõelise S-07 skeemi vastu."""
        _, run_folder = d1_extensions_output
        schema = _load_schema("S-07_monthly_balance_schema.json")
        with open(run_folder / "projections" / "monthly_balance_v1.json", encoding="utf-8") as f:
            data = json.load(f)
        jsonschema.validate(data, schema)

    def test_default_profile_no_extra_projections(self, d1_output: tuple) -> None:
        """Default profiiliga ei teki extra projection faile."""
        _, run_folder = d1_output
        assert not (run_folder / "projections" / "stats_v1.json").exists()
        assert not (run_folder / "projections" / "monthly_balance_v1.json").exists()

    def test_existing_artifacts_unchanged(
        self, d1_output: tuple, d1_extensions_output: tuple,
    ) -> None:
        """ML ja LLM väljundid on identsed default ja extensions_eval profiili vahel."""
        _, default_folder = d1_output
        _, ext_folder = d1_extensions_output

        with open(default_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            ml_default = f.read()
        with open(ext_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            ml_ext = f.read()
        assert ml_default == ml_ext, "ML CSV must be byte-identical across profiles"

        with open(default_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            llm_default = f.read()
        with open(ext_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            llm_ext = f.read()
        assert llm_default == llm_ext, "LLM JSON must be byte-identical across profiles"

    def test_audit_trail_in_report(self, d1_extensions_output: tuple) -> None:
        """report.json sisaldab extra_projections auditijälge."""
        _, run_folder = d1_extensions_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        assert "extra_projections" in report
        audit = report["extra_projections"]
        assert len(audit) == 2

        names = {a["name"] for a in audit}
        assert names == {"stats", "monthly_balance"}

        for entry in audit:
            assert entry["enabled"] is True
            assert entry["validation_result"] == "PASS"
            assert entry["item_count"] >= 1

    def test_report_validates_against_s05(self, d1_extensions_output: tuple) -> None:
        """extensions_eval raporti valideerimiskontroll S-05 skeemi vastu."""
        _, run_folder = d1_extensions_output
        schema = _load_schema("S-05_collected_report_schema.json")
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        jsonschema.validate(report, schema)

    def test_dropped_details_in_report(self, d1_output: tuple) -> None:
        """D1 has no dropped transactions."""
        _, run_folder = d1_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        dropped = report.get("dropped_details", [])
        assert len(dropped) == 0

    def test_dropped_details_in_summary(self, d1_output: tuple) -> None:
        """D1 has no dropped transactions in summary."""
        summary, _ = d1_output
        dropped = summary.get("dropped_details", [])
        assert len(dropped) == 0

    # --- JSON determinism ---

    def test_sv_json_sorted_keys(self, d1_output: tuple) -> None:
        """sv.json must use sorted keys for determinism."""
        _, run_folder = d1_output
        raw_text = (run_folder / "sv.json").read_text(encoding="utf-8")
        sv = json.loads(raw_text)
        reserialized = json.dumps(sv, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        assert raw_text == reserialized


# ---------------------------------------------------------------------------
# Determinism test: same input -> same output
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self, tmp_path: Path) -> None:
        """Running pipeline five times with same run_id produces identical output."""
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        out3 = tmp_path / "run3"
        out4 = tmp_path / "run4"
        out5 = tmp_path / "run5"

        ts = "2026-01-01T00:00:00Z"
        run_pipeline_fs(DATA_D1, out1, SPEC_DIR, run_id="determinism-test", created_at_utc=ts)
        run_pipeline_fs(DATA_D1, out2, SPEC_DIR, run_id="determinism-test", created_at_utc=ts)
        run_pipeline_fs(DATA_D1, out3, SPEC_DIR, run_id="determinism-test", created_at_utc=ts)
        run_pipeline_fs(DATA_D1, out4, SPEC_DIR, run_id="determinism-test", created_at_utc=ts)
        run_pipeline_fs(DATA_D1, out5, SPEC_DIR, run_id="determinism-test", created_at_utc=ts)

        # Find the run folders
        folder1 = list(out1.iterdir())[0]
        folder2 = list(out2.iterdir())[0]
        folder3 = list(out3.iterdir())[0]
        folder4 = list(out4.iterdir())[0]
        folder5 = list(out5.iterdir())[0]

        for relpath in ("sv.json", "report.json", "projections/ml_v1.csv", "projections/llm_context_v1.json"):
            content1 = (folder1 / relpath).read_text(encoding="utf-8")
            content2 = (folder2 / relpath).read_text(encoding="utf-8")
            content3 = (folder3 / relpath).read_text(encoding="utf-8")
            content4 = (folder4 / relpath).read_text(encoding="utf-8")
            content5 = (folder5 / relpath).read_text(encoding="utf-8")
            assert content1 == content2 == content3 == content4 == content5, f"{relpath} differs between runs"


# ---------------------------------------------------------------------------
# D6 — INV-09 duplicate record_id detection
# ---------------------------------------------------------------------------

class TestD6Deduplication:
    """Tests for INV-09 duplicate record_id detection using D6 dataset."""

    @pytest.fixture()
    def d6_output(self, tmp_path: Path) -> tuple[dict, Path]:
        data_dir = DATASETS_DIR / "D6_synth_dupes_seed99"
        summary = run_pipeline_fs(
            data_dir=data_dir,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d6-dedupe-test",
            created_at_utc=FIXED_TS,
        )
        return summary, Path(summary["run_folder"])

    def test_d6_outcome_partial_success(self, d6_output: tuple) -> None:
        """D6 has WARN-level dedupe drops → PARTIAL_SUCCESS, not FAILED."""
        summary, _ = d6_output
        assert summary["outcome"] == "PARTIAL_SUCCESS"

    def test_d6_inv09_warn_count(self, d6_output: tuple) -> None:
        """D6 should have INV-09 WARNs in the report."""
        _, run_folder = d6_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        assert report["summary"]["by_severity"]["WARN"] >= 3

    def test_d6_dropped_details_contain_duplicate(self, d6_output: tuple) -> None:
        """dropped_details should contain entries with 'duplicate record_id'."""
        summary, _ = d6_output
        dup_drops = [d for d in summary["dropped_details"] if "duplicate record_id" in d.get("drop_reason", "")]
        assert len(dup_drops) == 3

    def test_d6_dropped_details_have_record_id(self, d6_output: tuple) -> None:
        """Each dedupe drop should include the record_id that was duplicated."""
        summary, _ = d6_output
        dup_drops = [d for d in summary["dropped_details"] if "duplicate record_id" in d.get("drop_reason", "")]
        for drop in dup_drops:
            assert drop.get("record_id"), f"dedupe drop missing record_id: {drop}"

    def test_d6_no_duplicate_record_ids_in_sv(self, d6_output: tuple) -> None:
        """SV output should have no duplicate record_ids."""
        _, run_folder = d6_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        record_ids = [tx["record_id"] for tx in sv["transactions"]]
        assert len(record_ids) == len(set(record_ids)), "sv.json contains duplicate record_ids"

    def test_d6_no_duplicate_record_ids_in_ml_csv(self, d6_output: tuple) -> None:
        """ML CSV should have no duplicate record_ids."""
        _, run_folder = d6_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        record_ids = [r["record_id"] for r in rows]
        assert len(record_ids) == len(set(record_ids)), "ml_v1.csv contains duplicate record_ids"

    def test_d6_no_duplicate_ids_in_llm_context(self, d6_output: tuple) -> None:
        """LLM context should have no duplicate ids."""
        _, run_folder = d6_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        # Single account → direct object; multi-account → array
        contexts = [ctx] if isinstance(ctx, dict) and "tx" in ctx else ctx
        for c in contexts:
            ids = [tx["id"] for tx in c["tx"]]
            assert len(ids) == len(set(ids)), "llm_context contains duplicate ids"

    def test_d6_total_invariant(self, d6_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _ = d6_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]


# ---------------------------------------------------------------------------
# D4 — FAILED outcome (fail-gate from default.yaml)
# ---------------------------------------------------------------------------

class TestD4FailGate:
    """Tests for D4 dataset which should trigger the fail-gate → FAILED."""

    @pytest.fixture()
    def d4_output(self, tmp_path: Path) -> tuple[dict, Path]:
        data_dir = DATASETS_DIR / "D4_synth_errors_seed42"
        summary = run_pipeline_fs(
            data_dir=data_dir,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d4-fail-test",
            created_at_utc=FIXED_TS,
        )
        return summary, Path(summary["run_folder"])

    def test_d4_outcome_failed(self, d4_output: tuple) -> None:
        """D4 ERROR drop ratio > 5% → FAILED."""
        summary, _ = d4_output
        assert summary["outcome"] == "FAIL"

    def test_d4_has_drops(self, d4_output: tuple) -> None:
        """D4 should have exactly 4 dropped transactions."""
        summary, _ = d4_output
        assert summary["counts"]["transactions_dropped"] == 4

    def test_d4_drop_ratio_exceeds_threshold(self, d4_output: tuple) -> None:
        """The ERROR drop ratio must exceed 5% of total records."""
        summary, _ = d4_output
        counts = summary["counts"]
        ratio = counts["transactions_dropped"] / counts["transactions_total"]
        assert ratio > 0.05, f"Drop ratio {ratio:.2%} does not exceed 5%"

    def test_d4_total_invariant(self, d4_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _ = d4_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]

    def test_d4_by_severity_issues_covers_all_pipeline_errors(self, d4_output: tuple) -> None:
        """by_severity_issues peab katma KÕIK issues[]-i (mitte ainult tx-flage).

        D4 toodab 6 issue't: 1×S-00B (READ_INPUT, ERROR) + 2×C-01 (mapping drop,
        WARN) + 1×S-01 (VALIDATE_SCHEMA, ERROR) + 2×INV-01 (CHECK_INVARIANTS,
        ERROR). Vana by_severity näeb ainult viimaseid kahte.
        """
        summary, run_folder = d4_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        bsi = report["summary"]["by_severity_issues"]
        assert bsi == {"CRITICAL": 0, "ERROR": 4, "WARN": 2, "INFO": 0}
        assert summary["by_severity_issues"] == bsi

        # Vana by_severity jääb puutumata (tx-flagide loendur)
        assert report["summary"]["by_severity"]["ERROR"] == 2
        assert report["summary"]["by_severity"]["WARN"] == 0


# ---------------------------------------------------------------------------
# D2 — Mixed large dataset with INV-05 WARNs → PARTIAL_SUCCESS
# ---------------------------------------------------------------------------

DATA_D2 = DATASETS_DIR / "D2_synth_mixed_large"


class TestD2MixedLarge:
    """Tests for D2 dataset: 50 booked + 16 pending, INV-05 sign WARNs, no drops."""

    @pytest.fixture()
    def d2_output(self, tmp_path: Path) -> tuple[dict, Path]:
        summary = run_pipeline_fs(
            data_dir=DATA_D2,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d2-mixed-test",
            created_at_utc=FIXED_TS,
        )
        return summary, Path(summary["run_folder"])

    def test_d2_outcome_partial_success(self, d2_output: tuple) -> None:
        """D2 has INV-05 WARNs but no ERROR drops → PARTIAL_SUCCESS."""
        summary, _ = d2_output
        assert summary["outcome"] == "PARTIAL_SUCCESS"

    def test_d2_transaction_counts(self, d2_output: tuple) -> None:
        """D2: 50 booked + 16 pending = 66 total, all emitted."""
        summary, _ = d2_output
        counts = summary["counts"]
        assert counts["accounts_total"] == 1
        assert counts["transactions_total"] == 66
        assert counts["transactions_emitted_sv"] == 66
        assert counts["transactions_dropped"] == 0

    def test_d2_inv05_warns_present(self, d2_output: tuple) -> None:
        """D2 should have INV-05 WARN flags from sign mismatches."""
        _, run_folder = d2_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        inv05_count = sum(
            1 for tx in sv["transactions"]
            for flag in tx.get("flags", [])
            if flag["id"].startswith("INV-05")
        )
        assert inv05_count >= 1

    def test_d2_report_warn_count(self, d2_output: tuple) -> None:
        """D2 report should reflect WARN count from INV-05."""
        _, run_folder = d2_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        assert report["summary"]["by_severity"]["WARN"] >= 1

    def test_d2_no_drops(self, d2_output: tuple) -> None:
        """D2 has no ERROR-level issues → no drops."""
        summary, _ = d2_output
        assert len(summary["dropped_details"]) == 0

    def test_d2_ml_csv_row_count(self, d2_output: tuple) -> None:
        """ML CSV should have 66 rows (all BOOKED+PENDING)."""
        _, run_folder = d2_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 66

    def test_d2_ml_csv_sorted(self, d2_output: tuple) -> None:
        """ML CSV must be sorted by (account_id, value_date, record_id)."""
        _, run_folder = d2_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        sort_keys = [(r["account_id"], r["value_date"], r["record_id"]) for r in rows]
        assert sort_keys == sorted(sort_keys)

    def test_d2_total_invariant(self, d2_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _ = d2_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]


# ---------------------------------------------------------------------------
# D3 — Multi-account dataset with 2 transaction files → SUCCESS
# ---------------------------------------------------------------------------

DATA_D3 = DATASETS_DIR / "D3_synth_valid_seed42"


class TestD3MultiAccount:
    """Tests for D3: 2 accounts, 2 transaction files, 125 booked + 25 pending, SUCCESS."""

    @pytest.fixture()
    def d3_output(self, tmp_path: Path) -> tuple[dict, Path]:
        summary = run_pipeline_fs(
            data_dir=DATA_D3,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d3-multi-acct-test",
            created_at_utc=FIXED_TS,
        )
        return summary, Path(summary["run_folder"])

    def test_d3_outcome_success(self, d3_output: tuple) -> None:
        """D3 has valid data, no errors → SUCCESS."""
        summary, _ = d3_output
        assert summary["outcome"] == "SUCCESS"

    def test_d3_account_count(self, d3_output: tuple) -> None:
        """D3 has 2 accounts."""
        summary, _ = d3_output
        assert summary["counts"]["accounts_total"] == 2

    def test_d3_transaction_counts(self, d3_output: tuple) -> None:
        """D3: 125 booked + 25 pending = 150 total, all emitted."""
        summary, _ = d3_output
        counts = summary["counts"]
        assert counts["transactions_total"] == 150
        assert counts["transactions_emitted_sv"] == 150
        assert counts["transactions_dropped"] == 0

    def test_d3_sv_has_two_accounts(self, d3_output: tuple) -> None:
        """SV bundle should list 2 accounts."""
        _, run_folder = d3_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        assert len(sv["accounts"]) == 2

    def test_d3_sv_account_ibans(self, d3_output: tuple) -> None:
        """SV accounts should include DE and EE IBANs."""
        _, run_folder = d3_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        ibans = {a["iban"] for a in sv["accounts"]}
        assert "DE43321819600133890838" in ibans
        assert "EE402654235116155940" in ibans

    def test_d3_sv_transactions_from_both_accounts(self, d3_output: tuple) -> None:
        """SV transactions should reference both accounts."""
        _, run_folder = d3_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        account_ids = {tx["account_id"] for tx in sv["transactions"]}
        assert len(account_ids) == 2

    def test_d3_llm_contexts_per_account(self, d3_output: tuple) -> None:
        """LLM output should have contexts for both accounts."""
        _, run_folder = d3_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        if isinstance(ctx, list):
            assert len(ctx) == 2
        else:
            # Single dict with meta.account_id — check it's a list
            assert False, "Expected list of 2 LLM contexts for multi-account dataset"

    def test_d3_ml_csv_row_count(self, d3_output: tuple) -> None:
        """ML CSV should have 150 rows."""
        _, run_folder = d3_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 150

    def test_d3_no_drops(self, d3_output: tuple) -> None:
        """D3 has no dropped transactions."""
        summary, _ = d3_output
        assert len(summary["dropped_details"]) == 0

    def test_d3_total_invariant(self, d3_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _ = d3_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]


# ---------------------------------------------------------------------------
# D5 — Edge cases dataset → SUCCESS
# ---------------------------------------------------------------------------

DATA_D5 = DATASETS_DIR / "D5_synth_edges_seed99"


class TestD5EdgeCases:
    """Tests for D5: edge cases — zero/large/integer amounts, QC-1 INFO, long remittance."""

    @pytest.fixture()
    def d5_output(self, tmp_path: Path) -> tuple[dict, Path]:
        summary = run_pipeline_fs(
            data_dir=DATA_D5,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d5-edges-test",
            created_at_utc=FIXED_TS,
        )
        return summary, Path(summary["run_folder"])

    def test_d5_outcome_success(self, d5_output: tuple) -> None:
        """D5 edge cases are all valid — SUCCESS (QC-1 INFO flags do not affect outcome)."""
        summary, _ = d5_output
        assert summary["outcome"] == "SUCCESS"

    def test_d5_transaction_counts(self, d5_output: tuple) -> None:
        """D5: 28 booked + 5 pending = 33, all emitted."""
        summary, _ = d5_output
        counts = summary["counts"]
        assert counts["transactions_total"] == 33
        assert counts["transactions_emitted_sv"] == 33
        assert counts["transactions_dropped"] == 0

    def test_d5_no_drops(self, d5_output: tuple) -> None:
        """D5 edge cases are all valid — no drops expected."""
        summary, _ = d5_output
        assert len(summary["dropped_details"]) == 0

    def test_d5_qc01_info_present(self, d5_output: tuple) -> None:
        """D5 has a no-counterparty transaction → QC-1 INFO."""
        _, run_folder = d5_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        qc01_flags = [
            flag for tx in sv["transactions"]
            for flag in tx.get("flags", [])
            if flag["id"].startswith("QC-1")
        ]
        assert len(qc01_flags) >= 1

    def test_d5_zero_amount_handled(self, d5_output: tuple) -> None:
        """Zero amount transaction should be emitted without errors."""
        _, run_folder = d5_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        zero_txs = [tx for tx in sv["transactions"] if tx["amount"]["abs"] == "0.00" or tx["amount"]["abs"] == "0"]
        assert len(zero_txs) >= 1

    def test_d5_large_amount_handled(self, d5_output: tuple) -> None:
        """Large amount (9999999.999) should be emitted correctly."""
        _, run_folder = d5_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        large_txs = [tx for tx in sv["transactions"] if float(tx["amount"]["abs"]) > 1_000_000]
        assert len(large_txs) >= 1

    def test_d5_llm_remittance_truncation(self, d5_output: tuple) -> None:
        """Long remittance (307 chars) should be truncated to 160 in LLM projection."""
        _, run_folder = d5_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        contexts = [ctx] if isinstance(ctx, dict) and "tx" in ctx else ctx
        for c in contexts:
            for tx in c["tx"]:
                if tx.get("r") is not None:
                    assert len(tx["r"]) <= 160

    def test_d5_total_invariant(self, d5_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _ = d5_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]


# ---------------------------------------------------------------------------
# D7 — Standing orders / INFORMATION transactions
# ---------------------------------------------------------------------------

DATA_D7 = DATASETS_DIR / "D7_standing_orders_seed77"


class TestD7StandingOrders:
    """Tests for D7: 1 booked + 3 INFORMATION from standing_orders.json."""

    @pytest.fixture()
    def d7_output(self, tmp_path: Path) -> tuple[dict, Path]:
        summary = run_pipeline_fs(
            data_dir=DATA_D7,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d7-standing-orders-test",
            created_at_utc=FIXED_TS,
        )
        return summary, Path(summary["run_folder"])

    def test_d7_outcome_not_fail(self, d7_output: tuple) -> None:
        """D7 has valid data → SUCCESS or PARTIAL_SUCCESS."""
        summary, _ = d7_output
        assert summary["outcome"] in ("SUCCESS", "PARTIAL_SUCCESS")

    def test_d7_transaction_counts(self, d7_output: tuple) -> None:
        """D7: 1 booked + 3 information = 4 total, all emitted."""
        summary, _ = d7_output
        counts = summary["counts"]
        assert counts["accounts_total"] == 1
        assert counts["transactions_total"] == 4
        assert counts["transactions_emitted_sv"] == 4
        assert counts["transactions_dropped"] == 0

    def test_d7_information_transactions_in_sv(self, d7_output: tuple) -> None:
        """SV should contain 3 INFORMATION status transactions."""
        _, run_folder = d7_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        info_txs = [tx for tx in sv["transactions"] if tx["status"] == "INFORMATION"]
        assert len(info_txs) == 3

    def test_d7_value_date_fallback_from_next_execution_date(self, d7_output: tuple) -> None:
        """INFORMATION txs without valueDate should fallback to nextExecutionDate."""
        _, run_folder = d7_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        info_txs = [tx for tx in sv["transactions"] if tx["status"] == "INFORMATION"]
        for tx in info_txs:
            assert tx["value_date"] is not None, f"INFORMATION tx missing value_date: {tx['record_id']}"

    def test_d7_stadtwerke_value_date_fallback(self, d7_output: tuple) -> None:
        """Stadtwerke Berlin (no valueDate) → value_date = nextExecutionDate = 2025-02-01."""
        _, run_folder = d7_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        stadtwerke = [tx for tx in sv["transactions"] if tx.get("counterparty", {}).get("name") == "Stadtwerke Berlin"]
        assert len(stadtwerke) == 1
        assert stadtwerke[0]["value_date"] == "2025-02-01"

    def test_d7_vonovia_value_date_preferred(self, d7_output: tuple) -> None:
        """Vonovia SE (has valueDate=2025-02-01) → value_date = 2025-02-01 (preferred over nextExecDate)."""
        _, run_folder = d7_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        vonovia = [tx for tx in sv["transactions"] if tx.get("counterparty", {}).get("name") == "Vonovia SE"]
        assert len(vonovia) == 1
        assert vonovia[0]["value_date"] == "2025-02-01"

    def test_d7_allianz_value_date_fallback(self, d7_output: tuple) -> None:
        """Allianz (no valueDate) → value_date = nextExecutionDate = 2025-04-01."""
        _, run_folder = d7_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        allianz = [tx for tx in sv["transactions"] if tx.get("counterparty", {}).get("name") == "Allianz Versicherung"]
        assert len(allianz) == 1
        assert allianz[0]["value_date"] == "2025-04-01"

    def test_d7_information_excluded_from_ml(self, d7_output: tuple) -> None:
        """INFORMATION txs should NOT appear in ML projection (only BOOKED+PENDING)."""
        _, run_folder = d7_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1  # Only the 1 booked tx
        assert rows[0]["status"] == "BOOKED"

    def test_d7_information_excluded_from_llm(self, d7_output: tuple) -> None:
        """INFORMATION txs should NOT appear in LLM projection."""
        _, run_folder = d7_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        contexts = [ctx] if isinstance(ctx, dict) and "tx" in ctx else ctx
        for c in contexts:
            for tx in c["tx"]:
                assert tx["s"] != "INFORMATION"

    def test_d7_total_invariant(self, d7_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _ = d7_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]


# ---------------------------------------------------------------------------
# D8 — Load test with 10 000 transactions → SUCCESS + performance
# ---------------------------------------------------------------------------

DATA_D9 = DATASETS_DIR / "D9_synth_perf_seed9"
DATA_D8 = DATASETS_DIR / "D8_load_test_10k_seed88"

_D8_PERFORMANCE_SLO_MS = 10_000  # 10 seconds for 10k transactions


class TestD8LoadTest:
    """Tests for D8: 8000 booked + 2000 pending = 10000 total, SUCCESS, performance SLO."""

    @pytest.fixture(scope="class")
    def d8_output(self, tmp_path_factory) -> tuple[dict, Path, float]:
        """Run pipeline on D8 once per class and measure elapsed time."""
        import time
        tmp_path = tmp_path_factory.mktemp("d8")
        t0 = time.perf_counter()
        summary = run_pipeline_fs(
            data_dir=DATA_D8,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d8-load-test",
            created_at_utc=FIXED_TS,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return summary, Path(summary["run_folder"]), elapsed_ms

    def test_d8_outcome_success(self, d8_output: tuple) -> None:
        """D8 has all valid data → SUCCESS."""
        summary, _, _ = d8_output
        assert summary["outcome"] == "SUCCESS"

    def test_d8_transaction_counts(self, d8_output: tuple) -> None:
        """D8: 8000 booked + 2000 pending = 10000 total, all emitted."""
        summary, _, _ = d8_output
        counts = summary["counts"]
        assert counts["accounts_total"] == 1
        assert counts["transactions_total"] == 10_000
        assert counts["transactions_emitted_sv"] == 10_000
        assert counts["transactions_dropped"] == 0

    def test_d8_no_drops(self, d8_output: tuple) -> None:
        """D8 has no dropped transactions."""
        summary, _, _ = d8_output
        assert len(summary["dropped_details"]) == 0

    def test_d8_performance_within_slo(self, d8_output: tuple) -> None:
        """Pipeline with 10k transactions must finish within 10 seconds."""
        _, _, elapsed_ms = d8_output
        assert elapsed_ms <= _D8_PERFORMANCE_SLO_MS, (
            f"Pipeline took {elapsed_ms:.1f} ms for 10k txs — exceeds SLO of {_D8_PERFORMANCE_SLO_MS} ms"
        )

    def test_d8_sv_transaction_count(self, d8_output: tuple) -> None:
        """SV bundle should contain 10000 transactions."""
        _, run_folder, _ = d8_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        assert len(sv["transactions"]) == 10_000

    def test_d8_ml_csv_row_count(self, d8_output: tuple) -> None:
        """ML CSV should have 10000 rows (all BOOKED+PENDING)."""
        _, run_folder, _ = d8_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 10_000

    def test_d8_ml_csv_sorted(self, d8_output: tuple) -> None:
        """ML CSV must be sorted by (account_id, value_date, record_id)."""
        _, run_folder, _ = d8_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        sort_keys = [(r["account_id"], r["value_date"], r["record_id"]) for r in rows]
        assert sort_keys == sorted(sort_keys)

    def test_d8_ml_csv_row_id_sequential(self, d8_output: tuple) -> None:
        """ML row_ids must be sequential 1..10000."""
        _, run_folder, _ = d8_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        row_ids = [int(r["row_id"]) for r in rows]
        assert row_ids == list(range(1, 10_001))

    def test_d8_no_duplicate_record_ids(self, d8_output: tuple) -> None:
        """SV should have no duplicate record_ids among 10k transactions."""
        _, run_folder, _ = d8_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        record_ids = [tx["record_id"] for tx in sv["transactions"]]
        assert len(record_ids) == len(set(record_ids)), "D8 SV contains duplicate record_ids"

    def test_d8_total_invariant(self, d8_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _, _ = d8_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]

    def test_d8_report_no_errors(self, d8_output: tuple) -> None:
        """D8 should have zero ERROR severity issues."""
        _, run_folder, _ = d8_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        assert report["summary"]["by_severity"]["ERROR"] == 0

# ---------------------------------------------------------------------------
# Skaleeruvuse ajamõõtmised — päris andmestikud, päris I/O
# ---------------------------------------------------------------------------

class TestScalingTiming:
    """Skaleeruvuse ajamõõtmised päris andmestikel (run_pipeline_fs, päris I/O).

    Ei kontrolli SLO-t — eesmärk on skaleeruvuse tõendamine kolme punktiga.
    Käivita koos -s lipuga, et näha tulemusi:
        python -m pytest tests/tests.py::TestScalingTiming -v -s
    """

    @pytest.mark.parametrize("dataset,label,ceiling_ms", [
        ("D1_synth_valid_small",   "D1 (7 tx)",        2_000),
        ("D3_synth_valid_seed42",   "D3 (150 tx)",      3_000),
        ("D9_synth_perf_seed9",     "D9 (1 000 tx)",    8_000),
        ("D8_load_test_10k_seed88", "D8 (10 000 tx)",  40_000),
    ])
    def test_pipeline_timing(
        self, tmp_path: Path, dataset: str, label: str, ceiling_ms: int,
    ) -> None:
        """Mõõdab pipeline'i täielikku töötlusaega ja tagab lae regressioonide vastu."""
        data_dir = DATASETS_DIR / dataset

        t0 = time.perf_counter()
        summary = run_pipeline_fs(
            data_dir=data_dir,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        tx_count = summary["counts"]["transactions_total"]
        throughput = tx_count / elapsed_ms if elapsed_ms > 0 else 0

        print(f"\n[TIMING] {label}: {tx_count} tx | {elapsed_ms:.1f} ms | {throughput:.3f} tx/ms")
        assert elapsed_ms <= ceiling_ms, (
            f"{label} took {elapsed_ms:.0f} ms, ceiling is {ceiling_ms} ms"
        )


# ---------------------------------------------------------------------------
# Jõudluse võrdlusmõõtmised — mediaan + standardhälve, päris I/O
# ---------------------------------------------------------------------------

class TestBenchmarkD9D8:
    """Jõudluse võrdlusmõõtmised D9 (1 000 tx) ja D8 (10 000 tx) andmestikel.

    Metoodika: 1 proovijooks + 5 mõõdetud jooksu; tulemus on mediaan ja standardhälve.
    Kasutab run_pipeline_fs (päris failisüsteemi I/O).

    Ei kontrolli SLO-t — eesmärk on konkreetsete arvude saamine.
    Käivita:
        python -m pytest tests/tests.py::TestBenchmarkD9D8 -v -s
    """

    WARMUP_RUNS = 1
    MEASURED_RUNS = 5

    @pytest.mark.parametrize("dataset,label,expected_tx,median_ceiling_ms", [
        ("D9_synth_perf_seed9",     "D9 (1 000 tx)",  1_000,  4_000),
        ("D8_load_test_10k_seed88", "D8 (10 000 tx)", 10_000, 30_000),
    ])
    def test_benchmark(
        self,
        tmp_path_factory,
        dataset: str,
        label: str,
        expected_tx: int,
        median_ceiling_ms: int,
    ) -> None:
        """Mõõdab pipeline'i jõudlust päris andmestikul mitme jooksuga."""
        data_dir = DATASETS_DIR / dataset

        # Proovijooksud (soojendus)
        for i in range(self.WARMUP_RUNS):
            warmup_dir = tmp_path_factory.mktemp(f"{dataset}_warmup_{i}")
            run_pipeline_fs(
                data_dir=data_dir,
                output_dir=warmup_dir,
                spec_dir=SPEC_DIR,
                run_id=f"bench-warmup-{i}",
                created_at_utc=FIXED_TS,
            )

        # Mõõdetud jooksud
        measured_times: list[float] = []
        for i in range(self.MEASURED_RUNS):
            run_dir = tmp_path_factory.mktemp(f"{dataset}_run_{i}")
            t0 = time.perf_counter()
            summary = run_pipeline_fs(
                data_dir=data_dir,
                output_dir=run_dir,
                spec_dir=SPEC_DIR,
                run_id=f"bench-run-{i}",
                created_at_utc=FIXED_TS,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            measured_times.append(elapsed_ms)

            assert summary["counts"]["transactions_total"] == expected_tx

        # Statistika
        median_ms = statistics.median(measured_times)
        stdev_ms = statistics.stdev(measured_times)
        throughput = expected_tx / median_ms if median_ms > 0 else 0

        print(f"\n{'='*60}")
        print(f"[BENCHMARK] {label}")
        print(f"  Proovijooksud:    {self.WARMUP_RUNS}")
        print(f"  Mõõdetud jooksud: {self.MEASURED_RUNS}")
        print(f"  Kõik ajad (ms):   {[round(t, 2) for t in measured_times]}")
        print(f"  Mediaan:          {median_ms:.2f} ms")
        print(f"  Standardhälve:    {stdev_ms:.2f} ms")
        print(f"  Läbilaskevõime:   {throughput:.3f} tx/ms")
        print(f"{'='*60}")

        assert median_ms <= median_ceiling_ms, (
            f"{label} median {median_ms:.0f} ms exceeds ceiling {median_ceiling_ms} ms"
        )


# ---------------------------------------------------------------------------
# D11 — Real de-identified 2024 dataset (2 accounts) → SUCCESS
# ---------------------------------------------------------------------------
DATA_D11 = DATASETS_DIR / "D11_real_deid_2024"


class TestD11RealDeid2024:
    """Tests for D11: 2 real de-identified accounts, ~380 booked, 0 pending, SUCCESS."""

    @pytest.fixture()
    def d11_output(self, tmp_path: Path) -> tuple[dict, Path]:
        summary = run_pipeline_fs(
            data_dir=DATA_D11,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id="d11-real-deid-test",
            created_at_utc=FIXED_TS,
        )
        return summary, Path(summary["run_folder"])

    def test_d11_outcome_success(self, d11_output: tuple) -> None:
        """D11 has valid real data with correct sign convention → SUCCESS."""
        summary, _ = d11_output
        assert summary["outcome"] == "SUCCESS"

    def test_d11_account_count(self, d11_output: tuple) -> None:
        """D11 has 2 accounts."""
        summary, _ = d11_output
        assert summary["counts"]["accounts_total"] == 2

    def test_d11_transaction_counts(self, d11_output: tuple) -> None:
        """D11: all transactions emitted, none dropped."""
        summary, _ = d11_output
        counts = summary["counts"]
        assert counts["transactions_total"] > 0
        assert counts["transactions_emitted_sv"] == counts["transactions_total"]
        assert counts["transactions_dropped"] == 0

    def test_d11_sv_has_two_accounts(self, d11_output: tuple) -> None:
        """SV bundle should list 2 accounts."""
        _, run_folder = d11_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        assert len(sv["accounts"]) == 2

    def test_d11_sv_account_ibans(self, d11_output: tuple) -> None:
        """SV accounts should include both anonymised IBANs."""
        _, run_folder = d11_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        ibans = {a["iban"] for a in sv["accounts"]}
        assert "EE517700771002836491" in ibans
        assert "EE347700771003958274" in ibans

    def test_d11_sv_transactions_from_both_accounts(self, d11_output: tuple) -> None:
        """SV transactions should reference both accounts."""
        _, run_folder = d11_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        account_ids = {tx["account_id"] for tx in sv["transactions"]}
        assert len(account_ids) == 2

    def test_d11_llm_contexts_per_account(self, d11_output: tuple) -> None:
        """LLM output should have contexts for both accounts."""
        _, run_folder = d11_output
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        if isinstance(ctx, list):
            assert len(ctx) == 2
        else:
            assert False, "Expected list of 2 LLM contexts for multi-account dataset"

    def test_d11_ml_csv_row_count(self, d11_output: tuple) -> None:
        """ML CSV row count should equal total transactions."""
        summary, run_folder = d11_output
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == summary["counts"]["transactions_total"]

    def test_d11_no_drops(self, d11_output: tuple) -> None:
        """D11 has no dropped transactions."""
        summary, _ = d11_output
        assert len(summary["dropped_details"]) == 0

    def test_d11_total_invariant(self, d11_output: tuple) -> None:
        """total == emitted + dropped."""
        summary, _ = d11_output
        counts = summary["counts"]
        assert counts["transactions_total"] == counts["transactions_emitted_sv"] + counts["transactions_dropped"]


# ---------------------------------------------------------------------------
# Schema validation sweep across every dataset
# ---------------------------------------------------------------------------

ALL_DATASETS: list[str] = [
    "D1_synth_valid_small",
    "D2_synth_mixed_large",
    "D3_synth_valid_seed42",
    "D4_synth_errors_seed42",
    "D5_synth_edges_seed99",
    "D6_synth_dupes_seed99",
    "D7_standing_orders_seed77",
    "D8_load_test_10k_seed88",
    "D9_synth_perf_seed9",
    "D10_real_deid_oct16",
    "D11_real_deid_2024",
]


@pytest.mark.parametrize("dataset_name", ALL_DATASETS)
class TestSchemaValidationAllDatasets:
    """Valideerib iga andmestiku sv.json / ml_v1.csv / llm_context_v1.json / report.json."""

    @pytest.fixture()
    def run_folder(self, tmp_path: Path, dataset_name: str) -> Path:
        data_dir = DATASETS_DIR / dataset_name
        summary = run_pipeline_fs(
            data_dir=data_dir,
            output_dir=tmp_path,
            spec_dir=SPEC_DIR,
            run_id=f"schema-sweep-{dataset_name}",
            created_at_utc=FIXED_TS,
        )
        return Path(summary["run_folder"])

    def test_sv_conforms_to_s01(self, run_folder: Path) -> None:
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)
        jsonschema.validate(sv, _load_schema("S-01_sv_schema.json"))

    def test_ml_conforms_to_s02(self, run_folder: Path) -> None:
        schema = _load_schema("S-02_ml_projection_schema.json")
        with open(run_folder / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for raw_row in rows:
            row: dict = {**raw_row}
            row["row_id"] = int(row["row_id"])
            for field in ("booking_date", "counterparty_name", "remittance"):
                if row.get(field) == "":
                    row[field] = None
            jsonschema.validate(row, schema)

    def test_llm_conforms_to_s03(self, run_folder: Path) -> None:
        schema = _load_schema("S-03_llm_context_schema.json")
        with open(run_folder / "projections" / "llm_context_v1.json", encoding="utf-8") as f:
            ctx = json.load(f)
        if isinstance(ctx, list):
            for one in ctx:
                jsonschema.validate(one, schema)
        else:
            jsonschema.validate(ctx, schema)

    def test_report_conforms_to_s05(self, run_folder: Path) -> None:
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        jsonschema.validate(report, _load_schema("S-05_collected_report_schema.json"))
