# Testimine

Ülevaade testistrateegiast, testiklassidest ja käivitamisjuhistest.

---

## Testiklassid

### Unit-testid (`backend/tests/unit/`)

Kasutavad **fake-porte** — `FakeDatasetPort`, `FakeOutputPort`, `FakeSpecPort`, `FixedClock`.
Pipeline jookseb täielikult mälus, failisüsteemi ei puudutata.

| Fail | Testib |
|------|--------|
| `test_pipeline_with_fakes.py` | Pipeline äriloogika: mapping, invariandid, projektsioonid, outcome |
| `test_import_boundaries.py` | Kihistus: `domain/` ei impordi keelatud mooduleid (AST skaneerimine) |

Fake-portide allikad: `backend/tests/fakes/`.

### Integratsioonitestid (`backend/tests/tests.py`)

Kasutavad **päris FS-adaptereid** läbi `entrypoints/wiring_fs.py`.
Väljund kirjutatakse `tmp_path` kausta (pytest fixture).

Testivad end-to-end voo: sisend → SV → ML/LLM → raport → skeemivalideerimine.

### Arhitektuuritestid

| Fail | Testib |
|------|--------|
| `test_import_boundaries.py` | `domain/` importe AST-ga — keelatud impordid (pathlib, os, adapters) |
| `test_no_compat_imports.py` | Vana `backend/adapter/` compat-kiht on eemaldatud |

### QA / E2E valideerimine (`scripts/qa/`)

Eraldi skript `run_full_qa.py`, mis jooksutab järjest:

1. **Spetsifikatsiooni terviklikkus** — profiili viited, failide olemasolu
2. **Dataseti sisendi valideerimine** — skeemi- ja semantilised kontrollid
3. **Pipeline väljundi valideerimine** — skeemid + artefaktide ristkontroll
4. **Golden-snapshotide võrdlus** — SHA-256 võrdlus frozen goldenitega
5. **Determinismi suitsutestimine** — pipeline annab kordusjooksul sama tulemuse

---

## Käivitamine

### Kõik unit- ja integratsioonitestid

```bash
cd backend && python -m pytest tests/ -v
```

### Ainult unit-testid

```bash
cd backend && python -m pytest tests/unit/ -v
```

### QA (kõik datasetid)

```bash
python scripts/qa/run_full_qa.py
```

### QA (üks dataset)

```bash
python scripts/qa/run_full_qa.py --dataset D1_public_valid_small
```

### QA (kiire režiim — ainult D1 + D3)

```bash
python scripts/qa/run_full_qa.py --fast
```

### QA (ilma golden-võrdluseta)

```bash
python scripts/qa/run_full_qa.py --skip-golden
```

---

## Väljundikoodid (QA)

| Kood | Tähendus |
|------|----------|
| `0` | Kõik kontrollid läbitud |
| `1` | Üks või enam kontrolli ebaõnnestus |

---

## Eeldused

```bash
pip install jsonschema pyyaml
```
