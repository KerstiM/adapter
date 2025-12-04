from pathlib import Path
import json

from adapter.core import excel_statement_to_json


def test_excel_to_json_creates_transactions(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    excel_path = project_root / "data" / "bank.xlsx"
    out_file = tmp_path / "out.json"

    excel_statement_to_json(
        excel_path=excel_path,
        json_path=out_file,
        account_id="TEST-ACCOUNT",
        currency="INR",
        institution="TestBank",
    )

    assert out_file.exists()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "transactions" in data
    assert len(data["transactions"]) > 0

    first = data["transactions"][0]
    assert "amount" in first
    assert "booking_date" in first
    assert first["account_id"] == "TEST-ACCOUNT"
