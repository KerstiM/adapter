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
| `test_model_formatters.py` | C-04 mudeliformaatijad: XGBoost label-encoding, CatBoost native, Llama 3 / Mistral / Qwen promptimallid |
| `test_pipeline_with_model_target.py` | Pipeline end-to-end mudelisihtmärgiga: kõik 5 mudelit (3 LLM + 2 ML) |
| `test_scalability.py` | Skaleeritavus ja jõudlus: D8 (10k tehingut) ja D9 (1k tehingut) mediaanaeg, stddev, determinism |

Fake-portide allikad: `backend/tests/fakes/`. Kellaadapter testides: `adapters/testing/clock_fixed.py`.

### Integratsioonitestid (`backend/tests/tests.py`)

Kasutavad **päris FS-adaptereid** läbi `entrypoints/wiring_fs.py`.
Väljund kirjutatakse `tmp_path` kausta (pytest fixture).

Testivad end-to-end voo: sisend → SV → ML/LLM → raport → skeemivalideerimine.

### Arhitektuuritestid

| Fail | Testib |
|------|--------|
| `test_import_boundaries.py` | `domain/` importe AST-ga — keelatud impordid (pathlib, os, adapters) |

### SLI/SLO-testid (`backend/tests/sli_slo/`)

Kvaliteedimõõdikute automatiseeritud valideerimine. 72 testi, mis kontrollivad:

| SLI | Kirjeldus |
|-----|-----------|
| SLI-1 | Skeemikatvus: prioriteetsete väljade kaetus (≥ 0.95) |
| SLI-2 | Valideerimisläbilaskvus: puhta sisendi korral 100% |
| QC-2 | Drop-raporteerimine: kõik dropitud kirjed on `dropped_details[]`-s selgitatud |
| SLI-3 | Invariantide vastavus: kriitilisi rikkumisi 0 |
| Gate | Veadropide osakaal: <5% → PARTIAL_SUCCESS, ≥5% → FAIL |
| SLI-4 | Determinism: N=5 jooksu identsed artefaktid |
| SLI-5 | Auditiraja täielikkus: kõik kohustuslikud metaväljad olemas |
| SLI-6 | Viitejõudlus: D9 (1000 tx) mediaan ≤ 500 ms |

Tulemused: [`backend/tests/sli_slo/RESULTS.md`](../backend/tests/sli_slo/RESULTS.md).

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
