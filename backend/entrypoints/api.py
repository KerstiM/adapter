"""Minimal API server — stdlib only, zero extra dependencies.

Usage::

    cd backend
    python -m entrypoints.api          # http://127.0.0.1:8000

Environment variables:
    ADAPTER_HTTP_HOST   bind address (default: 127.0.0.1; set to 0.0.0.0
                        only when you understand the consequences — the API
                        returns per-transaction data including, for the
                        D10/D11 datasets, real bank-statement content).
    ADAPTER_HTTP_PORT   bind port (default: 8000).
    ADAPTER_CORS_ORIGINS comma-separated allowlist of allowed Origin headers
                        (default: http://localhost:5173,http://127.0.0.1:5173).
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from entrypoints.wiring_fs import run_pipeline_fs

ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS_DIR = ROOT / "datasets"
SPEC_DIR = ROOT / "spec"
OUTPUT_DIR = ROOT / ".pipeline_out"

MAX_BODY_BYTES = 1_000_000
MAX_PREAMBLE_CHARS = 2048
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def _allowed_origins() -> set[str]:
    raw = os.environ.get("ADAPTER_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return {o.strip() for o in raw.split(",") if o.strip()}


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


def _read_ml_preview(run_folder: Path) -> dict | None:
    csv_path = run_folder / "projections" / "ml_v1.csv"
    if not csv_path.exists():
        return None
    with csv_path.open() as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        rows = list(reader)
    return {"headers": headers, "rows": rows, "totalRows": len(rows)}


def _read_llm_preview(run_folder: Path, *, include_raw: bool = False) -> dict | None:
    """Read LLM context and transform to the shape the frontend expects.

    Raw format (single account):  { meta: {...}, tx: [...] }
    Raw format (multi-account):   [ { meta: {...}, tx: [...] }, ... ]
    Frontend:    { narrative, accountSummary: {periodStart, periodEnd, totalIncome,
                   totalExpenses, netFlow}, topCategories: [{category, total, count}] }

    The raw per-transaction context is omitted from the response by default
    because it can contain counterparty names and remittance text. Pass
    ``include_raw=True`` only when the caller is trusted (e.g. localhost dev).
    """
    llm_path = run_folder / "projections" / "llm_context_v1.json"
    if not llm_path.exists():
        return None
    llm_raw = json.loads(llm_path.read_text())
    raw_contexts = llm_raw if isinstance(llm_raw, list) else [llm_raw]

    # Multi-account datasets produce a list of contexts; use the first one for summary
    raw = raw_contexts[0] if raw_contexts else None
    if raw is None:
        return None

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
        "rawContexts": raw_contexts if include_raw else [],
    }


def _read_model_projections(run_folder: Path) -> list[dict]:
    """Read model-specific projection files with their content."""
    proj_dir = run_folder / "projections"
    if not proj_dir.exists():
        return []
    results = []
    for f in sorted(proj_dir.iterdir()):
        name = f.name
        # Model-specific files: ml_v1_{suffix}.json or llm_context_v1_{suffix}.json
        if name.startswith("ml_v1_") and name.endswith(".json"):
            suffix = name[len("ml_v1_"):-len(".json")]
            content = json.loads(f.read_text())
            results.append({
                "type": "ml",
                "modelSuffix": suffix,
                "filename": name,
                "content": content,
            })
        elif name.startswith("llm_context_v1_") and name.endswith(".json"):
            suffix = name[len("llm_context_v1_"):-len(".json")]
            content = json.loads(f.read_text())
            results.append({
                "type": "llm",
                "modelSuffix": suffix,
                "filename": name,
                "content": content,
            })
    return results


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin")
        if origin and origin in _allowed_origins():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> tuple[dict | None, tuple[dict, int] | None]:
        """Read and parse the request body.

        Returns ``(body, None)`` on success or ``(None, (error_dict, status))``
        when the body is too large or not valid JSON.
        """
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            return None, ({"error": "invalid Content-Length"}, 400)
        if length < 0:
            return None, ({"error": "invalid Content-Length"}, 400)
        if length > MAX_BODY_BYTES:
            return None, ({"error": "payload too large"}, 413)
        if length == 0:
            return {}, None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw), None
        except json.JSONDecodeError:
            return None, ({"error": "invalid json"}, 400)

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
            body, err = self._read_body()
            if err is not None:
                error_payload, status = err
                self._json_response(error_payload, status)
                return
            dataset_id = body.get("datasetId", "D1")

            # Optional model targeting from request body
            target_models_override = None
            target_llm = body.get("targetLlm")
            target_ml = body.get("targetMl")
            llm_preamble = body.get("llmPreamble")
            if llm_preamble is not None:
                if not isinstance(llm_preamble, str):
                    self._json_response({"error": "llmPreamble must be a string"}, 400)
                    return
                if len(llm_preamble) > MAX_PREAMBLE_CHARS:
                    self._json_response(
                        {"error": f"llmPreamble too long (max {MAX_PREAMBLE_CHARS} chars)"},
                        400,
                    )
                    return
            if target_llm or target_ml or llm_preamble:
                target_models_override = {}
                if target_llm:
                    target_models_override["llm"] = target_llm if isinstance(target_llm, list) else [target_llm]
                if target_ml:
                    target_models_override["ml"] = target_ml if isinstance(target_ml, list) else [target_ml]
                if llm_preamble:
                    target_models_override["llm_preamble"] = llm_preamble

            include_raw = bool(body.get("includeRaw", False))

            data_dir = _resolve_dataset(dataset_id)
            if data_dir is None:
                self._json_response({"error": f"Dataset '{dataset_id}' not found"}, 404)
                return

            t0 = time.perf_counter()
            try:
                summary = run_pipeline_fs(
                    data_dir, OUTPUT_DIR, spec_dir=SPEC_DIR,
                    target_models_override=target_models_override,
                )
            except FileNotFoundError:
                # Raised by spec adapters when a profile YAML or spec file
                # it references is missing on disk.  KeyError is intentionally
                # NOT caught here: a stray dict-access KeyError deep in the
                # pipeline is an internal bug, not a 404.
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                traceback.print_exc()
                self._json_response({
                    "error": "Required specification or dataset artefact not found",
                    "elapsed_ms": elapsed_ms,
                }, 404)
                return
            except Exception:
                # Everything else — including ValueError (e.g. unknown model
                # family in C-04, negative invariant counters in compute_metrics)
                # and RuntimeError — is a server/config fault by the time it
                # reaches here.  User-supplied fields (Content-Length, JSON body,
                # llmPreamble, dataset id) are validated + mapped to 4xx inline
                # above, before run_pipeline_fs is called.
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                traceback.print_exc()
                self._json_response({
                    "error": "Pipeline processing failed",
                    "elapsed_ms": elapsed_ms,
                }, 500)
                return
            elapsed_ms = round((time.perf_counter() - t0) * 1000)

            run_folder = Path(summary.pop("run_folder", ""))

            # Read real output files
            report = _read_report(run_folder)
            stage_log = report.get("summary", {}).get("by_stage", [])
            ml_preview = _read_ml_preview(run_folder)
            llm_preview = _read_llm_preview(run_folder, include_raw=include_raw)

            # Read model-specific projection files with content
            model_projections = _read_model_projections(run_folder)

            self._json_response({
                "result": summary,
                "elapsed_ms": elapsed_ms,
                "stageLog": stage_log,
                "mlPreview": ml_preview,
                "llmPreview": llm_preview,
                "modelProjections": model_projections,
            })
        else:
            self._json_response({"error": "Not found"}, 404)

    def log_message(self, fmt, *args):
        print(f"[api] {args[0]}")


if __name__ == "__main__":
    host = os.environ.get("ADAPTER_HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("ADAPTER_HTTP_PORT", "8000"))
    server = HTTPServer((host, port), Handler)
    print(f"API server running on http://{host}:{port}")
    server.serve_forever()
