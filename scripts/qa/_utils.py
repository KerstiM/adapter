"""Shared helpers for QA scripts: hashing, diff snippets, schema loading."""

import csv
import difflib
import hashlib
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = REPO_ROOT / "spec"
DATASETS_DIR = REPO_ROOT / "datasets"
FROZEN_VERSION = "v1.0.0"
FROZEN_DIR = REPO_ROOT / "frozen" / FROZEN_VERSION
GOLDEN_CREATED_AT = "2000-01-01T00:00:00Z"

# Pipeline output paths -> manifest artifact keys
ARTIFACT_MAP = [
    ("sv.json", "sv.json"),
    ("report.json", "report.json"),
    (str(Path("projections") / "ml_v1.csv"), "ml_v1.csv"),
    (str(Path("projections") / "llm_context_v1.json"), "llm_context_v1.json"),
]

STAGE_ORDER = [
    "READ_INPUT",
    "STANDARDIZE_TO_SV",
    "VALIDATE_SCHEMA",
    "CHECK_INVARIANTS",
    "PROJECT_ML",
    "PROJECT_LLM",
    "WRITE_OUTPUTS",
]


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

def diff_json_files(path_a: Path, path_b: Path, max_lines: int = 5) -> list[str]:
    """Return first N differing lines between two JSON files."""
    try:
        lines_a = path_a.read_text("utf-8").splitlines(keepends=True)
        lines_b = path_b.read_text("utf-8").splitlines(keepends=True)
    except Exception:
        return ["(could not read files for diff)"]

    diff = list(difflib.unified_diff(
        lines_a, lines_b,
        fromfile=str(path_a.name),
        tofile=str(path_b.name),
    ))
    if not diff:
        return []
    # Skip the --- / +++ header lines, show content diffs
    content_lines = [l.rstrip() for l in diff if l.startswith(("+", "-")) and not l.startswith(("---", "+++"))]
    return content_lines[:max_lines]


def diff_csv_first_row(path_a: Path, path_b: Path) -> str | None:
    """Return first differing row index between two CSV files, or None if identical."""
    try:
        with open(path_a, newline="", encoding="utf-8") as fa, \
             open(path_b, newline="", encoding="utf-8") as fb:
            reader_a = csv.reader(fa)
            reader_b = csv.reader(fb)
            for i, (row_a, row_b) in enumerate(zip(reader_a, reader_b)):
                if row_a != row_b:
                    return f"row {i} differs"
            # Check if one has more rows
            remaining_a = list(reader_a)
            remaining_b = list(reader_b)
            if remaining_a:
                return f"file A has {len(remaining_a)} extra rows after row {i}"
            if remaining_b:
                return f"file B has {len(remaining_b)} extra rows after row {i}"
    except Exception as e:
        return f"(diff error: {e})"
    return None


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def find_transaction_files(dataset_dir: Path) -> list[Path]:
    """Find all transactions*.json files in a dataset, excluding transactions_download.json."""
    return sorted(
        p for p in dataset_dir.glob("transactions*.json")
        if p.name != "transactions_download.json"
    )


def discover_datasets(filter_names: list[str] | None = None) -> list[Path]:
    """Find dataset directories under datasets/."""
    datasets = []
    for d in sorted(DATASETS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "accounts.json").exists():
            continue
        if not find_transaction_files(d):
            continue
        if filter_names:
            if not any(d.name.upper().startswith(f.upper()) for f in filter_names):
                continue
        datasets.append(d)
    return datasets


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_pipeline_deterministic(dataset_dir: Path, output_dir: Path, run_id: str | None = None) -> dict:
    """Run pipeline with fixed deterministic metadata."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from adapter.pipeline import run_pipeline

    ds_name = dataset_dir.name
    if run_id is None:
        run_id = f"GOLDEN_{ds_name}"
    return run_pipeline(
        data_dir=dataset_dir,
        output_dir=output_dir,
        run_id=run_id,
        created_at_utc=GOLDEN_CREATED_AT,
    )
