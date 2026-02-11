"""
Happy-path tests for the adapter pipeline.

Tests verify the full RAW -> SV -> ML/LLM projection flow
using data/D1 Berlin AIS fixtures against updated specs:
  S-01 (flat transactions, amount object, IN/OUT direction)
  C-02 (BOOKED+PENDING, row_id as int)
  C-03 (LLM context with short field names)
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
# Fixture: run pipeline once per test class
# ---------------------------------------------------------------------------

@pytest.fixture()
def d1_output(tmp_path: Path) -> tuple[dict, Path]:
    """Run pipeline on D1 and return (summary, output_dir)."""
    summary = run_pipeline(
        data_dir=DATA_D1,
        output_dir=tmp_path,
        run_id="test-run-001",
    )
    return summary, tmp_path


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
        # D1: transactions.json has 2 booked + 1 pending = 3
        # D1: standing_orders.json has 1 information (no valueDate -> skipped in mapping)
        # Total raw = 4, but only 3 are mappable (information tx lacks valueDate)
        assert counts["transactions_total"] == 4
        assert counts["accounts_total"] == 1
        assert counts["transactions_emitted_sv"] == 3

    def test_download_only_flagged(self, d1_output: tuple) -> None:
        """transactions_download.json should be detected and flagged, not processed."""
        summary, _ = d1_output
        download_flags = [f for f in summary["run_flags"] if f["id"] == "RUN_DOWNLOAD_ONLY"]
        assert len(download_flags) == 1

    # --- SV Bundle tests ---

    def test_sv_bundle_file_exists(self, d1_output: tuple) -> None:
        _, out = d1_output
        assert (out / "sv_bundle.json").exists()

    def test_sv_bundle_validates_against_schema(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)
        schema = _load_schema("S-01_sv_schema.json")
        jsonschema.validate(sv, schema)

    def test_sv_bundle_meta(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        meta = sv["meta"]
        assert meta["run_id"] == "test-run-001"
        assert meta["profile_id"] == "default"
        assert meta["spec_versions"]["S-01"] == "1.0.0"
        assert meta["spec_versions"]["C-01"] == "1.0.0"

    def test_sv_accounts_structure(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        assert len(sv["accounts"]) == 1
        acct = sv["accounts"][0]
        assert acct["iban"] == "DE2310010010123456788"
        assert acct["currency"] == "EUR"
        assert acct["name"] == "Main Account"

    def test_sv_transactions_flat_array(self, d1_output: tuple) -> None:
        """Transactions should be a top-level array, not nested in accounts."""
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        assert isinstance(sv["transactions"], list)
        # 2 booked + 1 pending = 3 (standing order information tx has no valueDate -> skipped)
        assert len(sv["transactions"]) == 3

    def test_sv_transaction_required_fields(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
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
        """Verify direction follows C-01 rules: debtorName->IN, creditorName->OUT."""
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
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
        """amount should be {currency, raw, signed, abs}."""
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
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
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["transactions"]:
            signed = float(tx["amount"]["signed"])
            if tx["direction"] == "OUT":
                assert signed <= 0, f"OUT amount should be negative: {tx['amount']}"
            elif tx["direction"] == "IN":
                assert signed >= 0, f"IN amount should be positive: {tx['amount']}"

    def test_sv_source_lineage(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        for tx in sv["transactions"]:
            assert tx["source"]["input_file"]
            assert tx["source"]["input_path"].startswith("$.transactions.")

    def test_sv_standing_order_skipped(self, d1_output: tuple) -> None:
        """standing_orders.json information tx lacks valueDate -> not in SV."""
        _, out = d1_output
        with open(out / "sv_bundle.json", encoding="utf-8") as f:
            sv = json.load(f)

        info_txs = [t for t in sv["transactions"] if t["status"] == "INFORMATION"]
        # Standing order has no valueDate, so it is not mapped to SV
        assert len(info_txs) == 0

    # --- ML projection tests ---

    def test_ml_csv_exists(self, d1_output: tuple) -> None:
        _, out = d1_output
        assert (out / "ml_projection.csv").exists()

    def test_ml_csv_correct_columns(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected = {
                "row_id", "account_id", "record_id", "status",
                "booking_date", "value_date", "direction", "currency",
                "signed_amount", "abs_amount", "counterparty_name", "remittance",
            }
            assert set(reader.fieldnames) == expected

    def test_ml_csv_booked_and_pending(self, d1_output: tuple) -> None:
        """ML projection includes BOOKED and PENDING (C-02 filter)."""
        _, out = d1_output
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        statuses = {r["status"] for r in rows}
        assert "BOOKED" in statuses
        assert "PENDING" in statuses
        # 2 booked + 1 pending = 3 (INFORMATION excluded)
        assert len(rows) == 3

    def test_ml_csv_row_id_is_sequential(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        row_ids = [int(r["row_id"]) for r in rows]
        assert row_ids == list(range(1, len(rows) + 1))

    def test_ml_csv_sorted_deterministically(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "ml_projection.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        sort_keys = [(r["account_id"], r["value_date"], r["record_id"]) for r in rows]
        assert sort_keys == sorted(sort_keys)

    # --- LLM context tests ---

    def test_llm_context_exists(self, d1_output: tuple) -> None:
        _, out = d1_output
        assert (out / "llm_context.json").exists()

    def test_llm_context_validates_against_schema(self, d1_output: tuple) -> None:
        _, out = d1_output
        schema = _load_schema("S-03_llm_context_schema.json")
        with open(out / "llm_context.json", encoding="utf-8") as f:
            ctx = json.load(f)
        jsonschema.validate(ctx, schema)

    def test_llm_context_meta(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "llm_context.json", encoding="utf-8") as f:
            ctx = json.load(f)

        assert ctx["meta"]["run_id"] == "test-run-001"
        assert ctx["meta"]["iban"] == "DE2310010010123456788"
        assert ctx["meta"]["currency"] == "EUR"

    def test_llm_context_tx_fields(self, d1_output: tuple) -> None:
        """LLM tx items should use short field names: id, d, s, dir, a, c, cp, r."""
        _, out = d1_output
        with open(out / "llm_context.json", encoding="utf-8") as f:
            ctx = json.load(f)

        for tx in ctx["tx"]:
            assert "id" in tx
            assert "d" in tx   # value_date
            assert "s" in tx   # status
            assert "dir" in tx # direction
            assert "a" in tx   # amount.signed
            assert "c" in tx   # currency

    def test_llm_context_booked_and_pending(self, d1_output: tuple) -> None:
        _, out = d1_output
        with open(out / "llm_context.json", encoding="utf-8") as f:
            ctx = json.load(f)
        statuses = {tx["s"] for tx in ctx["tx"]}
        assert "BOOKED" in statuses
        assert "PENDING" in statuses
        # 2 booked + 1 pending = 3 (INFORMATION excluded)
        assert len(ctx["tx"]) == 3

    def test_schema_validation_issues_expected(self, d1_output: tuple) -> None:
        """standing_orders.json triggers S-00B issue (information tx lacks valueDate)."""
        summary, _ = d1_output
        schema_issues = [i for i in summary["issues"] if "validation" in i.lower()]
        # Only the standing_orders.json S-00B issue is expected
        assert len(schema_issues) == 1
        assert "valueDate" in schema_issues[0]


# ---------------------------------------------------------------------------
# Determinism test: same input -> same output
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self, tmp_path: Path) -> None:
        """Running pipeline twice with same run_id produces identical output."""
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        run_pipeline(DATA_D1, out1, run_id="determinism-test")
        run_pipeline(DATA_D1, out2, run_id="determinism-test")

        for fname in ("sv_bundle.json", "ml_projection.csv", "llm_context.json"):
            content1 = (out1 / fname).read_text(encoding="utf-8")
            content2 = (out2 / fname).read_text(encoding="utf-8")
            assert content1 == content2, f"{fname} differs between runs"
