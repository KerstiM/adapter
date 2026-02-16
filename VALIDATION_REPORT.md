# Schema/Contract Validation Report

## Datasets Tested

| Dataset | Type | Outcome | Input Valid | Output Valid |
|---------|------|---------|-------------|--------------|
| D1_public_valid_small | Happy path (1 account, 7 tx) | SUCCESS | Yes | Yes |
| D2_public_mixed_large | Mixed warnings (1 account, 66 tx) | PARTIAL_SUCCESS | Yes | Yes |
| D3_synth_valid_seed42 | Multi-account (2 accounts, 150 tx) | SUCCESS | Yes | Yes |
| D4_synth_errors_seed42 | Error dataset (invalid currency/dates) | FAIL | No (intentional) | Yes |
| D5_synth_edges_seed99 | Edge cases (1 account, 33 tx) | PARTIAL_SUCCESS | Yes | Yes |
| D6_synth_dupes_seed99 | Duplicates (1 account, 21 tx) | PARTIAL_SUCCESS | Yes | Yes |

## Mismatches Found and Fixes Applied

### 1. S-05 (report schema) — Major structural mismatch

**Problem:** S-05 expected a structure that differed from actual `report.json` in multiple ways:

| Aspect | S-05 Expected | Actual Output |
|--------|---------------|---------------|
| Top-level `report_schema_version` | Required | Missing |
| `run` fields | `sv_schema_version`, `mapping_version`, `ruleset_version` | `profile_id`, `data_dir` |
| `outcome` | Top-level object with `status` + `stop_reason` | String inside `summary` |
| `summary.by_stage` | Array of `{stage, errors, warnings, infos}` | Dict keyed by stage name |
| `issues` | Array of structured objects with `code`, `severity`, `stage`, `message`, `refs` | Array of plain strings |
| `run_flags` | Not in schema | Present in output |
| `dropped_details` | Not in schema | Present in output |
| `summary.counts` | 4 fields only | 6 fields (extra: `ml_rows`, `llm_contexts`) |
| Outcome enum | `FAIL` | `FAILED` |
| `metrics` | Required array | Not produced |

**Fix chosen:** Updated **both** pipeline code and S-05 schema (reconciliation approach):
- **Pipeline (`pipeline.py`)**: Changed outcome enum `FAILED`→`FAIL`; converted `issues` from plain strings to structured objects; converted `by_stage` from dict to array; added `report_schema_version`, `stop_reason`; restructured `run` to include `sv_schema_version`/`mapping_version`/`ruleset_version` instead of `profile_id`/`data_dir`; moved `outcome` to top-level object.
- **Schema (`S-05`)**: Updated to match the reconciled output shape — added `run_flags`, `dropped_details`, expanded `counts` to include `ml_rows`+`llm_contexts`, removed `metrics` (not produced by prototype).
- **Why:** The pipeline's actual behavior was the intended prototype design. S-05 was a draft that hadn't been reconciled with the implementation. The `metrics` field was aspirational but not yet implemented, so it was removed from S-05 rather than adding dead code.

### 2. S-03 (LLM context schema) — Array vs object mismatch

**Problem:** S-03 defined `type: "object"` (single context), but the pipeline outputs an array when datasets have multiple accounts (D3 has 2 accounts → array of 2 context objects). Single-account datasets get a plain object.

**Fix chosen:** Updated S-03 schema to use `oneOf` — accepts either a single `LLMContext` object or an array of `LLMContext` objects. The `LLMContext` definition was extracted into `$defs`.

**Why:** This matches the actual pipeline behavior (line 920-923 of `pipeline.py`): single-account → object, multi-account → array. Forcing single-object output would lose data for multi-account datasets. Updated C-03 contract to document the cardinality rule.

### 3. default.yaml — Incorrect schema file paths

**Problem:** Profile referenced `S-00_berlin_accounts.schema.json` and `S-00_berlin_transactions.schema.json`, but actual files are named `S-00A_...` and `S-00B_...`. Worked at runtime only because of a fuzzy suffix-matching fallback in `_resolve_spec_path()`.

**Fix chosen:** Updated `default.yaml` paths to use correct filenames (`S-00A_...`, `S-00B_...`).

**Why:** Relying on fallback matching is fragile. Direct paths are correct and explicit.

### 4. C-03 contract — Outdated shape description

**Problem:** C-03 referenced `$.accounts[0].account_id` etc., implying single-account output only.

**Fix chosen:** Updated C-03 to document `cardinality` rule and changed `$.accounts[0].*` references to `@current_account.*` to reflect per-account iteration.

## Validation Results (Post-Fix)

All 6 datasets × 6 artifacts = 36 validations:
- **35 PASS** — all output artifacts validate against their schemas
- **1 expected FAIL** — D4 `transactions.json` vs S-00B (intentionally invalid raw input)

## Files Changed

| File | Change |
|------|--------|
| `backend/adapter/pipeline.py` | Report structure: outcome enum, structured issues, by_stage array, report_schema_version, stop_reason |
| `backend/run_adapter.py` | Display structured issues |
| `spec/schemas/S-05_collected_report_schema.json` | Complete rewrite to match reconciled report.json shape |
| `spec/schemas/S-03_llm_context_schema.json` | Added oneOf for single object / array support |
| `spec/contracts/C-03_sv_to_llm.yaml` | Documented multi-account cardinality |
| `spec/profiles/default.yaml` | Fixed S-00A/S-00B file path references |
| `scripts/validate_artifacts.py` | New end-to-end validation script |
