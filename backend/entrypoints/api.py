"""Minimal Flask API — exposes the adapter pipeline to the frontend.

Usage::

    cd backend
    python -m entrypoints.api          # http://localhost:5000
"""

from __future__ import annotations

import time
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from entrypoints.wiring_fs import run_pipeline_fs

ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS_DIR = ROOT / "datasets"
SPEC_DIR = ROOT / "spec"
OUTPUT_DIR = ROOT / ".backend" / "out"

app = Flask(__name__)
CORS(app)


def _resolve_dataset(dataset_id: str) -> Path | None:
    """Find dataset directory by short ID (e.g. 'D1') or full name."""
    for d in sorted(DATASETS_DIR.iterdir()):
        if d.is_dir() and (d.name == dataset_id or d.name.startswith(dataset_id + "_")):
            if (d / "accounts.json").exists():
                return d
    return None


@app.get("/api/datasets")
def list_datasets():
    datasets = []
    for d in sorted(DATASETS_DIR.iterdir()):
        if d.is_dir() and (d / "accounts.json").exists():
            short_id = d.name.split("_")[0]
            datasets.append({"id": short_id, "name": d.name})
    return jsonify(datasets)


@app.post("/api/run")
def run_pipeline():
    body = request.get_json(force=True)
    dataset_id = body.get("datasetId", "D1")

    data_dir = _resolve_dataset(dataset_id)
    if data_dir is None:
        return jsonify({"error": f"Dataset '{dataset_id}' not found"}), 404

    t0 = time.perf_counter()
    summary = run_pipeline_fs(data_dir, OUTPUT_DIR, spec_dir=SPEC_DIR)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    summary.pop("run_folder", None)
    return jsonify({"result": summary, "elapsed_ms": elapsed_ms})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
