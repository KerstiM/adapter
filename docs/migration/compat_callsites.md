# Legacy compat layer callsites (`backend/adapter/`)

> Generated 2026-02-21.
> Purpose: inventory of every place that imports or references the
> **backward-compatibility wrapper** `backend/adapter/pipeline.py`
> (filesystem-signature `run_pipeline(data_dir, output_dir, ...)`).
> These must be migrated before the `adapter/` (singular) package can be removed.

---

## 1. Import sites (`from adapter.pipeline import run_pipeline`)

| # | File | Line | Context |
|---|------|------|---------|
| 1 | `backend/run_adapter.py` | 13 | CLI entry point |
| 2 | `backend/tests/tests.py` | 24 | Main test suite |
| 3 | `scripts/validate_artifacts.py` | 100 | Artifact validation helper |
| 4 | `scripts/compare_golden.py` | 25 | Golden-file comparison script |
| 5 | `scripts/export_golden.py` | 31 | Golden-file export script |
| 6 | `scripts/qa/_utils.py` | 151 | QA utility function |

## 2. Call sites (compat signature)

All callers use the filesystem-based signature exposed by the compat wrapper:

```python
run_pipeline(data_dir, output_dir, run_id=None, created_at_utc=None) -> dict
```

| # | File | Line(s) | Signature used |
|---|------|---------|----------------|
| 1 | `backend/run_adapter.py` | 80 | `run_pipeline(data_dir, output_dir)` |
| 2 | `backend/tests/tests.py` | 47, 472–473, 495, 572 | `run_pipeline(DATA_D1, out, ...)` — some calls include `run_id` and `created_at_utc` |
| 3 | `scripts/validate_artifacts.py` | 101 | `run_pipeline(dataset_dir, output_dir)` |
| 4 | `scripts/compare_golden.py` | 102 | `run_pipeline(...)` |
| 5 | `scripts/export_golden.py` | 80 | `run_pipeline(...)` |
| 6 | `scripts/qa/_utils.py` | 156 | `run_pipeline(...)` |

## 3. Documentation references to `backend/adapter/pipeline.py`

| # | File | Line(s) | Note |
|---|------|---------|------|
| 1 | `README.md` | 52 | Feature checklist |
| 2 | `VALIDATION_REPORT.md` | 70 | Report structure docs |
| 3 | `docs/plans/variant-a-project-structure.md` | 269–284 | Architecture plan (6 refs) |

## 4. Internal wiring (not a migration target)

`backend/adapter/pipeline.py` itself imports from the **adapters** (plural) package
to construct the concrete port implementations:

| Line | Import |
|------|--------|
| 22 | `from adapters.fs.clock_impl import FixedClock, SystemClock` |
| 23 | `from adapters.fs.dataset_fs import FsDatasetAdapter` |
| 24 | `from adapters.fs.output_fs import FsOutputAdapter` |
| 25 | `from adapters.fs.spec_fs import FsSpecAdapter` |

These are part of the compat layer itself and will disappear with it.

## 5. Re-export

`backend/adapter/__init__.py` re-exports `run_pipeline` from `.pipeline`,
so `from adapter import run_pipeline` also works (no additional callers found
using this form).

---

## Summary

- **6 files** import from the compat layer.
- **~10 distinct call sites** use the filesystem-based signature.
- **3 docs** reference `backend/adapter/pipeline.py` by path.
- Migration means switching each caller to use `application.pipeline.run_pipeline`
  directly (port-based signature) and constructing adapters at the call site.
