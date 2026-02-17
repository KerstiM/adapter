# QA Scripts

End-to-end quality assurance for the adapter pipeline.

## `run_full_qa.py` — Full QA Entrypoint

Runs all verification stages in sequence:

1. **Spec integrity** — profile references, file existence, version fields
2. **Dataset input validation** — schema + semantic checks on raw inputs
3. **Pipeline output validation** — schema validation + cross-artifact consistency
4. **Golden snapshot verification** — SHA-256 comparison against frozen goldens
5. **Determinism smoke check** — pipeline produces identical output on repeated runs

### Quick start

```bash
# Run all datasets (from repo root)
python scripts/qa/run_full_qa.py

# Single dataset
python scripts/qa/run_full_qa.py --dataset D1_public_valid_small

# Multiple datasets
python scripts/qa/run_full_qa.py --dataset D1,D2

# Fast mode (D1 + D3 only)
python scripts/qa/run_full_qa.py --fast

# Skip golden comparison (validate only)
python scripts/qa/run_full_qa.py --skip-golden
```

### Windows PowerShell

```powershell
# Run all datasets
python scripts\qa\run_full_qa.py

# Single dataset
python scripts\qa\run_full_qa.py --dataset D1_public_valid_small

# Fast mode
python scripts\qa\run_full_qa.py --fast

# Skip golden comparison
python scripts\qa\run_full_qa.py --skip-golden
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | One or more checks failed |

### Output format

```
SPEC: PASS
DATASETS: PASS/FAIL
OUTPUTS: PASS/FAIL
GOLDENS: PASS/FAIL
DETERMINISM: PASS/FAIL
```

Failures include compact per-dataset and per-file details.

## Other QA scripts

| Script | Purpose |
|--------|---------|
| `build_spec_lock.py` | Generate `frozen/v1.0.0/spec.lock.json` from profile |
| `freeze_goldens.py` | Freeze pipeline outputs into `frozen/v1.0.0/golden/` |
| `verify_goldens.py` | Verify frozen goldens are still reproducible |

### Prerequisites

Install Python dependencies (from repo root):

```bash
pip install jsonschema pyyaml
```
