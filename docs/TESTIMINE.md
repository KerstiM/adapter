# Testimine

Ülevaade testistrateegiast, testiklassidest ja käivitamisjuhistest.

---

## Testiklassid

- **Unit-testid** (`backend/tests/unit/`) — kasutavad fake-porte (`FakeDatasetPort`, `FakeOutputPort`, `FakeSpecPort`, `FixedClock`); pipeline jookseb mälus, ilma FS-ita.
- **Integratsioonitestid** (`backend/tests/test_integration_fs.py`) — päris FS-adapterid läbi `entrypoints/wiring_fs.py`, väljund `tmp_path` kausta.
- **Arhitektuuritestid** — `test_import_boundaries.py` skaneerib AST-iga `domain/` importe, et keelatud moodulid (pathlib, os, adapters) ei lekiks tuumkihti.
- **SLI/SLO-testid** (`backend/tests/sli_slo/`) — vt mõõdikute tabel allpool.
- **QA / E2E** (`scripts/qa/run_full_qa.py`) — koondskript, mis kontrollib spec-terviklikkust, sisendi valideerimist, väljundit, golden-snapshotite ja determinismi.

### SLI/SLO-testid (`backend/tests/sli_slo/`)

| Mõõdik | Tähendus | Sihttase |
|--------|----------|----------|
| SLI-1 | Skeemikatvus — prioriteetsete SV väljade kaetus | ≥ 0.95 |
| SLI-2 | Valideerimisläbilaskvus — puhta sisendi alleshoid | = 1.0 |
| SLI-3 | Invariantide vastavus — ERROR-rikkumiste puudumine | kriitilisi = 0 |
| SLI-4 | Determinism — N=5 jooksu baidi-identsed artefaktid | identsus |
| SLI-5 | Auditiraja täielikkus — kohustuslikud metaväljad raportis | kõik olemas |
| SLI-6 | Viitejõudlus — D9 (1000 tx) jooksuaja mediaan | ≤ 500 ms |
| QC-2 | Drop-raporteerimine — iga dropp on `dropped_details[]`-s | kõik kaetud |
| Gate | Fail-värav — ERROR-drop osakaal sisendist | ≥ 5% → FAIL |

Tulemused: [`backend/tests/sli_slo/RESULTS.md`](../backend/tests/sli_slo/RESULTS.md).

---

## Testifailide ülevaade

**Kokku 452 testi 19 failis.**

| Testifail | Tests | Mida katab |
|-----------|-------|------------|
| `tests/test_integration_fs.py` | 168 | End-to-end pipeline päris FS-adapteritega (kõik datasetid, mudelid, profiilid, golden-võrdlused) |
| `tests/sli_slo/test_sli_slo.py` | 89 | SLI-1..SLI-6, QC-2, Gate (sihttasemed, väravakäitumine, tundlikkusanalüüs) |
| `tests/unit/test_scalability.py` | 39 | UK3 laiendatavus (C-05, C-06, Gemma, register-dispatch) + jõudluse mediaan (D8/D9) + chat-token strip |
| `tests/unit/test_pipeline_with_fakes.py` | 23 | Pipeline mälu-režiimis fake-portidega (äriloogika, mapping, projektsioonid, outcome) |
| `tests/unit/test_model_formatters.py` | 21 | C-04 formaatijad: Llama 3 / Mistral / ChatML / Gemma promptimallid + XGBoost / CatBoost kodeeringud |
| `tests/unit/test_invariants_r01.py` | 14 | R-01 invariandid INV-01..INV-05 + INV-09 dedupe |
| `tests/unit/test_llm_preview_view.py` | 12 | LLM preview view-builder (puhas funktsioon, ekstraheeritud api.py-st) |
| `tests/unit/test_api_security.py` | 12 | HTTP-handler turvapiir: CORS, body-suurus, preamble-pikkus, rawContexts opt-in |
| `tests/unit/test_pipeline_with_model_target.py` | 11 | Pipeline end-to-end mudelisihtmärgiga (3 LLM + 2 ML) |
| `tests/unit/test_json_format.py` | 11 | `stable_json` / `api_json` / `compact_json` formaadid (golden/API/LLM-prompt) |
| `tests/unit/test_dataset_resolver.py` | 9 | Jagatud dataset-name resolver CLI ja API jaoks (case-insensitive, underscore-fence) |
| `tests/unit/test_severity_counters.py` | 9 | `_count_severities` kernel + `count_flags_by_severity` + `count_issues_by_severity` |
| `tests/unit/test_input_edge_cases.py` | 8 | Piiripealsed sisendid (EDGE-01..EDGE-08) |
| `tests/unit/test_quality_checks.py` | 6 | QC-1 INFO-tasemel kontroll (ei mõjuta staatust) |
| `tests/unit/test_c05_stats.py` | 6 | C-05 statistika projektsioon (extensions_eval profiil) |
| `tests/unit/test_c06_monthly_balance.py` | 5 | C-06 kuubilanss projektsioon |
| `tests/unit/test_spec_fs_path_traversal.py` | 4 | Spec-adapter path traversal kaitse (`../../etc/passwd`) |
| `tests/unit/test_adapter_parity.py` | 4 | Fake vs päris FS-adapterite paariskontroll |
| `tests/unit/test_import_boundaries.py` | 1 | `domain/` ei impordi keelatud mooduleid (AST) |

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
python scripts/qa/run_full_qa.py --dataset D1_synth_valid_small
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

Sõltuvused: `pip install -r backend/requirements.txt` (vt README "Käivitamine").
