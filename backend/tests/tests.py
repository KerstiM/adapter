"""
Happy-path tests for the adapter pipeline.

Tests verify the full RAW -> SV -> ML/LLM projection flow
using data/D1 Berlin AIS fixtures against specs:
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
DATA_D1 = PROJECT_ROOT / "data" / "D1"

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
            assert report["summary"]["by_stage"]["CHECK_INVARIANTS"]["warnings"] >= 1

    def test_D_d1_counts(self, d1_output: tuple) -> None:
        """D) D1: accounts_total=1, transactions_total=4, dropped=0.
        Note: D1 has 2 booked + 1 pending + 1 information = 4 raw.
        The information tx lacks valueDate and is unmappable -> emitted=3, dropped=0.
        """
        summary, _ = d1_output
        counts = summary["counts"]
        assert counts["accounts_total"] == 1
        assert counts["transactions_total"] == 4
        assert counts["transactions_dropped"] == 0
        assert counts["transactions_emitted_sv"] == 3


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
        assert counts["transactions_total"] == 4
        assert counts["accounts_total"] == 1
        assert counts["transactions_emitted_sv"] == 3

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
        assert acct["iban"] == "DE2310010010123456788"
        assert acct["currency"] == "EUR"
        assert acct["name"] == "Main Account"

    def test_sv_transactions_flat_array(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        assert isinstance(sv["transactions"], list)
        assert len(sv["transactions"]) == 3

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

        # "Example 1" has creditorName (John Miles) -> OUT
        assert by_remittance["Example 1"]["direction"] == "OUT"
        assert by_remittance["Example 1"]["counterparty"]["role"] == "CREDITOR"

        # "Example 2" has debtorName (Paul Simpson) -> IN
        assert by_remittance["Example 2"]["direction"] == "IN"
        assert by_remittance["Example 2"]["counterparty"]["role"] == "DEBTOR"

    def test_sv_amount_object_structure(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        by_remittance = {}
        for tx in sv["transactions"]:
            if tx.get("remittance"):
                by_remittance[tx["remittance"]] = tx

        # Example 1: OUT, raw=256.67, signed should be negative
        ex1 = by_remittance["Example 1"]["amount"]
        assert ex1["raw"] == "256.67"
        assert ex1["signed"] == "-256.67"
        assert ex1["abs"] == "256.67"
        assert ex1["currency"] == "EUR"

        # Example 2: IN, raw=343.01, signed should be positive
        ex2 = by_remittance["Example 2"]["amount"]
        assert ex2["raw"] == "343.01"
        assert ex2["signed"] == "343.01"
        assert ex2["abs"] == "343.01"

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

    def test_sv_inv05_on_example1(self, d1_output: tuple) -> None:
        """Example 1: raw=256.67 (positive) but direction=OUT -> INV-05 WARN flag."""
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        by_remittance = {}
        for tx in sv["transactions"]:
            if tx.get("remittance"):
                by_remittance[tx["remittance"]] = tx

        ex1_flags = by_remittance["Example 1"]["flags"]
        inv05 = [f for f in ex1_flags if f["id"].startswith("INV-05")]
        assert len(inv05) == 1
        assert inv05[0]["severity"] == "WARN"

    def test_sv_source_lineage(self, d1_output: tuple) -> None:
        _, run_folder = d1_output
        with open(run_folder / "sv.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["transactions"]:
            assert tx["source"]["input_file"]
            assert tx["source"]["input_path"].startswith("$.transactions.")

    def test_sv_standing_order_skipped(self, d1_output: tuple) -> None:
        """standing_orders.json information tx lacks valueDate -> not in SV."""
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
        actual_stages = set(report["summary"]["by_stage"].keys())
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
        assert len(rows) == 3

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
        assert ctx["meta"]["iban"] == "DE2310010010123456788"
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
        assert len(ctx["tx"]) == 3

    def test_schema_validation_issues_expected(self, d1_output: tuple) -> None:
        """standing_orders.json triggers S-00B issue (information tx lacks valueDate)."""
        summary, _ = d1_output
        schema_issues = [i for i in summary["issues"] if "validation" in i.lower()]
        assert len(schema_issues) == 1
        assert "valueDate" in schema_issues[0]

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
