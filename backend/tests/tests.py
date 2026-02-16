"""
Happy-path tests for the adapter pipeline.

Tests verify the full RAW -> SV -> ML/LLM projection flow
using datasets/D1_public_valid_small Berlin AIS fixtures against specs:
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
from pathlib import Path

import jsonschema
import pytest

from adapter.pipeline import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = PROJECT_ROOT / "spec"
DATASETS_DIR = PROJECT_ROOT / "datasets"
DATA_D1 = DATASETS_DIR / "D1_public_valid_small"

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
    summary = run_pipeline(
        data_dir=DATA_D1,
        output_dir=tmp_path,
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
        """D) D1: accounts_total=1, transactions_total=8, dropped=0.
        Note: D1 has 5 booked + 2 pending (transactions.json) +
        1 information standing order with nextExecutionDate (standing_orders.json) = 8 raw.
        The information tx uses nextExecutionDate as value_date fallback -> emitted=8, dropped=0.
        Invariant: total == emitted + dropped.
        """
        summary, _ = d1_output
        counts = summary["counts"]
        assert counts["accounts_total"] == 1
        assert counts["transactions_total"] == 8
        assert counts["transactions_dropped"] == 0
        assert counts["transactions_emitted_sv"] == 8
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
        assert counts["transactions_total"] == 8
        assert counts["accounts_total"] == 1
        assert counts["transactions_emitted_sv"] == 8

    def test_download_only_flagged(self, d1_output: tuple) -> None:
        """transactions_download.json should be detected and flagged, not processed."""
        summary, _ = d1_output
        download_flags = [f for f in summary["run_flags"] if f["id"] == "RUN_DOWNLOAD_ONLY"]
        assert len(download_flags) == 1

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
        assert len(sv["transactions"]) == 8

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

    def test_sv_inv05_on_standing_order(self, d1_output: tuple) -> None:
        """Standing order: raw=256.67 (positive) but direction=OUT -> INV-05 WARN flag."""
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        by_remittance = {}
        for tx in sv["transactions"]:
            if tx.get("remittance"):
                by_remittance[tx["remittance"]] = tx

        so_flags = by_remittance["Standing order example"]["flags"]
        inv05 = [f for f in so_flags if f["id"].startswith("INV-05")]
        assert len(inv05) == 1
        assert inv05[0]["severity"] == "WARN"

    def test_sv_source_lineage(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["transactions"]:
            assert tx["source"]["input_file"]
            assert tx["source"]["input_path"].startswith("$.transactions.")

    def test_sv_standing_order_mapped(self, d1_output: tuple) -> None:
        """standing_orders.json information tx uses nextExecutionDate as value_date fallback -> mapped into SV."""
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        info_txs = [t for t in sv["transactions"] if t["status"] == "INFORMATION"]
        assert len(info_txs) == 1
        assert info_txs[0]["value_date"] == "2025-03-24"

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

    # --- ML projection tests ---

    def test_ml_csv_exists(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        assert (run_folder / "projections" / "ml_v1.csv").exists()

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
        """standing_orders.json has nextExecutionDate -> S-00C schema passes."""
        summary, _ = d1_output
        schema_issues = [i for i in summary["issues"] if "validation" in i.lower()]
        assert len(schema_issues) == 0

    def test_dropped_details_in_report(self, d1_output: tuple) -> None:
        """No transactions dropped — standing order uses nextExecutionDate fallback."""
        _, run_folder = d1_output
        with open(run_folder / "report.json", encoding="utf-8") as f:
            report = json.load(f)

        dropped = report.get("dropped_details", [])
        assert len(dropped) == 0

    def test_dropped_details_in_summary(self, d1_output: tuple) -> None:
        """Summary dropped_details must match report — none dropped."""
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
        """Running pipeline twice with same run_id produces identical output."""
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        ts = "2026-01-01T00:00:00Z"
        run_pipeline(DATA_D1, out1, run_id="determinism-test", created_at_utc=ts)
        run_pipeline(DATA_D1, out2, run_id="determinism-test", created_at_utc=ts)

        # Find the run folders
        folder1 = list(out1.iterdir())[0]
        folder2 = list(out2.iterdir())[0]

        for relpath in ("sv.json", "report.json", "projections/ml_v1.csv", "projections/llm_context_v1.json"):
            content1 = (folder1 / relpath).read_text(encoding="utf-8")
            content2 = (folder2 / relpath).read_text(encoding="utf-8")
            assert content1 == content2, f"{relpath} differs between runs"


# ---------------------------------------------------------------------------
# D6 — INV-09 duplicate record_id detection
# ---------------------------------------------------------------------------

class TestD6Deduplication:
    """Tests for INV-09 duplicate record_id detection using D6 dataset."""

    @pytest.fixture()
    def d6_output(self, tmp_path: Path) -> tuple[dict, Path]:
        data_dir = DATASETS_DIR / "D6_synth_dupes_seed99"
        summary = run_pipeline(
            data_dir=data_dir,
            output_dir=tmp_path,
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
        summary = run_pipeline(
            data_dir=data_dir,
            output_dir=tmp_path,
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
