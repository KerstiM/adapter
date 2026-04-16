"""Fake vs. FS adapter parity: sama sisend peab andma sama väljundi.

Kaitseb fakes/ ja adapters/fs/ komplektide vahelise semantilise triivi eest.
Kui FakeSpecPort või FakeOutputPort semantika lahkneb FS-adapteritest, siis
``backend/tests/unit/`` testid tunduksid rohelised, aga päris pipeline
kukuks. See test tuvastab sellise lahknevuse.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from application.pipeline import run_pipeline
from entrypoints.wiring_fs import run_pipeline_fs
from tests.fakes import (
    FakeDatasetPort,
    FakeOutputPort,
    FakeSpecPort,
    FakeValidationPort,
    FixedClock,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPEC_DIR = PROJECT_ROOT / "spec"
DATA_D1 = PROJECT_ROOT / "datasets" / "D1_synth_valid_small"
FIXED_TS = "2026-01-01T00:00:00Z"
FIXED_RUN_ID = "parity-run"


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def fake_vs_fs() -> tuple[FakeOutputPort, Path]:
    """Run pipeline twice on D1: once with fakes, once with FS adapters."""
    accounts = _read_json(DATA_D1 / "accounts.json")
    transactions = _read_json(DATA_D1 / "transactions.json")

    # In-memory run
    dataset = FakeDatasetPort(
        accounts=accounts,
        transaction_reports={"transactions.json": transactions},
    )
    fake_out = FakeOutputPort()
    clock = FixedClock(fixed_utc=FIXED_TS, fixed_run_id=FIXED_RUN_ID)

    # Match the input_dir normalization used by run_pipeline_fs: repo-relative posix.
    repo_root = SPEC_DIR.resolve().parent
    input_dir = str(DATA_D1.resolve().relative_to(repo_root).as_posix())

    run_pipeline(
        dataset=dataset,
        out=fake_out,
        spec=FakeSpecPort(),
        clock=clock,
        validator=FakeValidationPort(),
        dataset_id="D1_synth_valid_small",
        input_dir=input_dir,
    )

    # FS run
    fs_tmp = Path(pytest.fs_tmp_dir)  # type: ignore[attr-defined]
    summary_fs = run_pipeline_fs(
        data_dir=DATA_D1,
        output_dir=fs_tmp,
        spec_dir=SPEC_DIR,
        run_id=FIXED_RUN_ID,
        created_at_utc=FIXED_TS,
    )
    fs_run_folder = Path(summary_fs["run_folder"])
    return fake_out, fs_run_folder


@pytest.fixture(scope="module", autouse=True)
def _fs_tmp_dir(tmp_path_factory: pytest.TempPathFactory) -> None:
    pytest.fs_tmp_dir = tmp_path_factory.mktemp("parity_fs")  # type: ignore[attr-defined]


class TestAdapterParity:
    """Iga väljundartefakt peab olema in-memory ja FS-adapterite vahel identne."""

    def test_sv_bundle_identical(self, fake_vs_fs: tuple[FakeOutputPort, Path]) -> None:
        fake_out, fs_run = fake_vs_fs
        fs_sv = _read_json(fs_run / "sv.json")
        assert fake_out.sv == fs_sv

    def test_report_identical(self, fake_vs_fs: tuple[FakeOutputPort, Path]) -> None:
        fake_out, fs_run = fake_vs_fs
        fs_report = _read_json(fs_run / "report.json")
        assert fake_out.report == fs_report

    def test_llm_context_identical(
        self, fake_vs_fs: tuple[FakeOutputPort, Path],
    ) -> None:
        fake_out, fs_run = fake_vs_fs
        fs_llm = _read_json(fs_run / "projections" / "llm_context_v1.json")
        # Fake stores single-context for 1-account dataset; FS writes the same.
        assert fake_out.llm == fs_llm

    def test_ml_rows_identical(
        self, fake_vs_fs: tuple[FakeOutputPort, Path],
    ) -> None:
        fake_out, fs_run = fake_vs_fs
        with open(fs_run / "projections" / "ml_v1.csv", encoding="utf-8") as f:
            fs_rows = list(csv.DictReader(f))

        # Normalize both sides: CSV reader yields strings; fake stores native types.
        def _normalize(rows: list[dict]) -> list[dict]:
            normalised = []
            for r in rows:
                row = dict(r)
                if "row_id" in row and row["row_id"] != "" and row["row_id"] is not None:
                    row["row_id"] = int(row["row_id"])
                for field in ("booking_date", "counterparty_name", "remittance"):
                    if row.get(field) in ("", None):
                        row[field] = None
                    else:
                        row[field] = str(row[field])
                for k, v in list(row.items()):
                    if v is None:
                        continue
                    if k in ("row_id",):
                        continue
                    row[k] = str(v)
                normalised.append(row)
            return normalised

        assert _normalize(fake_out.ml or []) == _normalize(fs_rows)
