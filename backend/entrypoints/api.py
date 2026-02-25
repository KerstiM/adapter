"""Minimal API server — stdlib only, zero extra dependencies.

Usage::

    cd backend
    python -m entrypoints.api          # http://localhost:5000
"""

from __future__ import annotations

import csv
import io
import json
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from entrypoints.wiring_fs import run_pipeline_fs

ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS_DIR = ROOT / "datasets"
SPEC_DIR = ROOT / "spec"
OUTPUT_DIR = ROOT / ".pipeline_out"


def _resolve_dataset(dataset_id: str) -> Path | None:
    for d in sorted(DATASETS_DIR.iterdir()):
        if d.is_dir() and (d.name == dataset_id or d.name.startswith(dataset_id + "_")):
            if (d / "accounts.json").exists():
                return d
    return None


def _read_report(run_folder: Path) -> dict:
    report_path = run_folder / "report.json"
    if report_path.exists():
        return json.loads(report_path.read_text())
    return {}


def _read_ml_preview(run_folder: Path, max_rows: int = 10) -> dict | None:
    csv_path = run_folder / "projections" / "ml_v1.csv"
    if not csv_path.exists():
        return None
    with csv_path.open() as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        rows = []
        total = 0
        for row in reader:
            total += 1
            if len(rows) < max_rows:
                rows.append(row)
    return {"headers": headers, "rows": rows, "totalRows": total}


def _read_llm_preview(run_folder: Path) -> dict | None:
    """Read LLM context and transform to the shape the frontend expects.

    Raw format:  { meta: {account_id, iban, currency, ...}, tx: [{a, c, d, dir, ...}] }
    Frontend:    { narrative, accountSummary: {periodStart, periodEnd, totalIncome,
                   totalExpenses, netFlow}, topCategories: [{category, total, count}] }
    """
    llm_path = run_folder / "projections" / "llm_context_v1.json"
    if not llm_path.exists():
        return None
    raw = json.loads(llm_path.read_text())

    meta = raw.get("meta", {})
    txs = raw.get("tx", [])

    if not txs:
        return None

    # Compute account summary from transactions
    dates = [t["d"] for t in txs if t.get("d")]
    total_income = 0.0
    total_expenses = 0.0
    category_map: dict[str, dict] = {}

    for tx in txs:
        amount = float(tx.get("a", 0))
        direction = tx.get("dir", "")
        reason = tx.get("r", "Other") or "Other"

        if direction == "IN" or amount > 0:
            total_income += abs(amount)
        else:
            total_expenses += abs(amount)

        # Group by reason as category
        cat = reason.split()[0] if reason else "Other"
        if cat not in category_map:
            category_map[cat] = {"category": cat, "total": 0.0, "count": 0}
        category_map[cat]["total"] += amount
        category_map[cat]["count"] += 1

    net_flow = total_income - total_expenses
    period_start = min(dates) if dates else "—"
    period_end = max(dates) if dates else "—"

    top_categories = sorted(category_map.values(), key=lambda c: abs(c["total"]), reverse=True)

    iban = meta.get("iban", "")
    currency = meta.get("currency", "EUR")
    narrative = (
        f"Account {iban}: {len(txs)} transactions "
        f"from {period_start} to {period_end}. "
        f"Total income {total_income:.2f} {currency}, "
        f"expenses {total_expenses:.2f} {currency}, "
        f"net flow {net_flow:+.2f} {currency}."
    )

    return {
        "narrative": narrative,
        "accountSummary": {
            "periodStart": period_start,
            "periodEnd": period_end,
            "totalIncome": total_income,
            "totalExpenses": total_expenses,
            "netFlow": net_flow,
        },
        "topCategories": top_categories,
    }


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/datasets":
            datasets = []
            for d in sorted(DATASETS_DIR.iterdir()):
                if d.is_dir() and (d / "accounts.json").exists():
                    short_id = d.name.split("_")[0]
                    datasets.append({"id": short_id, "name": d.name})
            self._json_response(datasets)
        else:
            self._json_response({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            dataset_id = body.get("datasetId", "D1")

            data_dir = _resolve_dataset(dataset_id)
            if data_dir is None:
                self._json_response({"error": f"Dataset '{dataset_id}' not found"}, 404)
                return

            t0 = time.perf_counter()
            try:
                summary = run_pipeline_fs(data_dir, OUTPUT_DIR, spec_dir=SPEC_DIR)
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                traceback.print_exc()
                self._json_response({
                    "error": f"Pipeline failed: {exc}",
                    "elapsed_ms": elapsed_ms,
                }, 500)
                return
            elapsed_ms = round((time.perf_counter() - t0) * 1000)

            run_folder = Path(summary.pop("run_folder", ""))

            # Read real output files
            report = _read_report(run_folder)
            stage_log = report.get("summary", {}).get("by_stage", [])
            ml_preview = _read_ml_preview(run_folder)
            llm_preview = _read_llm_preview(run_folder)

            self._json_response({
                "result": summary,
                "elapsed_ms": elapsed_ms,
                "stageLog": stage_log,
                "mlPreview": ml_preview,
                "llmPreview": llm_preview,
            })
        else:
            self._json_response({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        print(f"[api] {args[0]}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), Handler)
    print("API server running on http://localhost:5000")
    server.serve_forever()
