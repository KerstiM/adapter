"""
Happy-path tests for the adapter pipeline.

Tests verify the full RAW -> SV -> ML/LLM -> report flow
using data/D1 Berlin AIS fixtures.
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


def _load_schema(name: str) -> dict:
    with open(SPEC_DIR / "schemas" / name, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Happy-path: full pipeline on D1
# ---------------------------------------------------------------------------

@pytest.fixture()
def d1_output(tmp_path: Path) -> tuple[dict, Path]:
    """Run pipeline on D1 and return (report, output_dir)."""
    report = run_pipeline(
        data_dir=DATA_D1,
        output_dir=tmp_path,
        provider_id="fixture",
        run_id="test-run-001",
    )
    return report, tmp_path


class TestHappyPathPipeline:
    """End-to-end happy-path tests using D1 fixtures."""

    def test_outcome_not_fail(self, d1_output: tuple) -> None:
        report, _ = d1_output
        assert report["outcome"]["status"] in ("SUCCESS", "PARTIAL_SUCCESS")

    def test_all_booked_emitted(self, d1_output: tuple) -> None:
        report, _ = d1_output
        counts = report["summary"]["counts"]
        # D1 has 5 booked + 1 pending = 6 total
        assert counts["transactions_total"] == 6
        assert counts["accounts_total"] == 1
        # All should be emitted (no drops expected in happy path)
        assert counts["transactions_emitted_sv"] == 6
        assert counts["transactions_dropped"] == 0

    def test_sv_bundle_file_exists(self, d1_output: tuple) -> None:
        _, out = d1_output
        assert (out / "sv_bundle.json").exists()

    def test_sv_bundle_validates_against_schema(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)
        schema = _load_schema("S-01_sv_schema.json")
        jsonschema.validate(sv, schema)

    def test_sv_bundle_structure(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        assert sv["sv_schema_version"] == "1.0.0"
        assert sv["run"]["run_id"] == "test-run-001"
        assert sv["run"]["adapter_version"] == "0.1.0"
        assert sv["run"]["source"]["source_type"] == "psd2_json_fixture"
        assert len(sv["accounts"]) == 1

        acct = sv["accounts"][0]
        assert acct["account_id"] == "fixture:3dc3d5b3-7023-4848-9853-f5400a64e80f"
        assert acct["account_ref"]["iban"] == "DE2310010010123456788"
        assert acct["account_ref"]["currency"] == "EUR"

    def test_sv_transactions_have_required_fields(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["accounts"][0]["transactions"]:
            assert tx["record_id"]
            assert tx["account_id"]
            assert tx["booking_time_utc"].endswith("Z")
            assert tx["amount"]
            assert tx["currency"] == "EUR"
            assert tx["direction"] in ("DEBIT", "CREDIT")
            assert tx["origin"]["source_format"] == "berlin_ais_json"
            assert isinstance(tx["flags"], list)

    def test_sv_direction_inference(self, d1_output: tuple) -> None:
        """Verify direction is correctly inferred from Berlin AIS data."""
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        txs = sv["accounts"][0]["transactions"]
        # Find by description_norm
        by_desc = {tx["description_norm"]: tx for tx in txs}

        # "example 1" has creditorName -> DEBIT (we pay to creditor)
        assert by_desc["example 1"]["direction"] == "DEBIT"
        # "example 2" has debtorName -> CREDIT (we receive from debtor)
        assert by_desc["example 2"]["direction"] == "CREDIT"

    def test_sv_amount_sign_matches_direction(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["accounts"][0]["transactions"]:
            amt = float(tx["amount"])
            if tx["direction"] == "DEBIT":
                assert amt < 0, f"DEBIT amount should be negative: {tx['amount']}"
            elif tx["direction"] == "CREDIT":
                assert amt > 0, f"CREDIT amount should be positive: {tx['amount']}"

    # --- ML projection tests ---

    def test_ml_csv_exists(self, d1_output: tuple) -> None:
        _, out = d1_output
        assert (out / "ml_projection.csv").exists()

    def test_ml_csv_correct_columns(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected = {
                "row_id", "account_id", "booking_time_utc",
                "amount", "amount_abs", "direction", "currency",
                "desc_norm", "month", "weekday",
            }
            assert set(reader.fieldnames) == expected

    def test_ml_csv_booked_only(self, d1_output: tuple) -> None:
        """ML projection should only contain BOOKED transactions."""
        _, out = d1_output
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        # D1 has 5 booked transactions
        assert len(rows) == 5

    def test_ml_csv_rows_validate_against_schema(self, d1_output: tuple) -> None:
        _, out = d1_output
        schema = _load_schema("S-02_ml_projection_schema.json")
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # Convert month/weekday to int for schema validation
                obj = dict(row)
                obj["month"] = int(obj["month"]) if obj["month"] else None
                obj["weekday"] = int(obj["weekday"]) if obj["weekday"] else None
                jsonschema.validate(obj, schema)

    def test_ml_csv_sorted_deterministically(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        sort_keys = [(r["account_id"], r["booking_time_utc"], r["row_id"]) for r in rows]
        assert sort_keys == sorted(sort_keys)

    # --- LLM context tests ---

    def test_llm_context_exists(self, d1_output: tuple) -> None:
        _, out = d1_output
        llm_files = list(out.glob("llm_context_*.json"))
        assert len(llm_files) == 1

    def test_llm_context_validates_against_schema(self, d1_output: tuple) -> None:
        _, out = d1_output
        schema = _load_schema("S-03_llm_context_schema.json")
        for llm_file in out.glob("llm_context_*.json"):
            with open(llm_file, encoding="utf-8") as f:
                ctx = json.load(f)
            jsonschema.validate(ctx, schema)

    def test_llm_context_structure(self, d1_output: tuple) -> None:
        _, out = d1_output
        llm_file = list(out.glob("llm_context_*.json"))[0]
        with open(llm_file, encoding="utf-8") as f:
            ctx = json.load(f)

        assert ctx["meta"]["run_id"] == "test-run-001"
        assert ctx["meta"]["projection_id"] == "llm_context"
        assert ctx["meta"]["windowing"]["mode"] == "LAST_N"
        assert ctx["account_context"]["currency"] == "EUR"
        # Only BOOKED transactions
        assert len(ctx["transactions"]) == 5

    def test_llm_context_booked_only(self, d1_output: tuple) -> None:
        _, out = d1_output
        llm_file = list(out.glob("llm_context_*.json"))[0]
        with open(llm_file, encoding="utf-8") as f:
            ctx = json.load(f)
        # 5 booked transactions in D1
        assert len(ctx["transactions"]) == 5

    # --- Report tests ---

    def test_report_file_exists(self, d1_output: tuple) -> None:
        _, out = d1_output
        assert (out / "report.json").exists()

    def test_report_validates_against_schema(self, d1_output: tuple) -> None:
        _, out = d1_output
        schema = _load_schema("S-05_collected_report_schema.json")
        with open(out / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        jsonschema.validate(report, schema)

    def test_report_metrics_present(self, d1_output: tuple) -> None:
        report, _ = d1_output
        assert len(report["metrics"]) >= 1
        sli4 = report["metrics"][0]
        assert sli4["id"] == "SLI4_transaction_pass_rate"
        assert sli4["value"] == 1.0  # all pass in happy path

    def test_report_no_errors(self, d1_output: tuple) -> None:
        report, _ = d1_output
        sev = report["summary"]["by_severity"]
        assert sev["CRITICAL"] == 0
        assert sev["ERROR"] == 0


# ---------------------------------------------------------------------------
# Determinism test: same input -> same output
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self, tmp_path: Path) -> None:
        """Running pipeline twice with same run_id produces identical output."""
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        run_pipeline(DATA_D1, out1, provider_id="fixture", run_id="determinism-test")
        run_pipeline(DATA_D1, out2, provider_id="fixture", run_id="determinism-test")

        for fname in ("sv_bundle.json", "ml_projection.csv", "report.json"):
            content1 = (out1 / fname).read_text(encoding="utf-8")
            content2 = (out2 / fname).read_text(encoding="utf-8")
            assert content1 == content2, f"{fname} differs between runs"

        # LLM context
        llm1 = sorted(out1.glob("llm_context_*.json"))
        llm2 = sorted(out2.glob("llm_context_*.json"))
        assert len(llm1) == len(llm2)
        for f1, f2 in zip(llm1, llm2):
            assert f1.read_text() == f2.read_text(), f"LLM context differs"
