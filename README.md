# Adapter / standardiseerimiskiht

Prototüüp loeb Berlin Group / PSD2 AIS stiilis sisendfailid ja teisendab need **standardiseeritud vaheesituseks (SV)**.
SV põhjal tuletatakse deterministlikud **projektsioonid** (ML CSV ja LLM context JSON) ning koostatakse **koondraport**.

Normatiivne käitumine on kirjeldatud `spec/` kataloogi versioonitud skeemide, lepingute ja reeglitega.

## Käivitamine

```bash
# Eeldused: Python 3.11+, sõltuvused paigaldatud
cd backend && pip install -r requirements.txt

# Üks dataset (prefix-match: D1 → D1_public_valid_small)
python backend/run_adapter.py --data D1 --out backend/out

# Kõik datasetid
for d in datasets/D*; do python backend/run_adapter.py --data "$d" --out backend/out; done
```

CLI argumendid:
- `--data / -d` — dataseti nimi (nt `D1`, `D4`) või kaustatee. Vaikimisi: `D1_public_valid_small`.
- `--out / -o` — väljundi juurkaust. Vaikimisi: `<repo>/.backend/out/`.

Väljund tekib jooksu-kausta alla:

```
<out>/<timestamp>_<run_id>/
    sv.json                          # kanooniline SVBundle
    report.json                      # koondraport (outcome, issues, counts)
    projections/
        ml_v1.csv                    # ML projektsioon
        llm_context_v1.json          # LLM kontekst
```

Tootmisjooksul on `<timestamp>` päris süsteemiaeg (UTC, ISO 8601) ja `<run_id>` juhuslik UUID4-põhine identifikaator.
Testides kasutatakse fikseeritud kella — vt allpool jaotist **Determinism ja kell**.

Täpsem käivitusjuhend: [`docs/runbook.md`](docs/runbook.md).

## Testide käivitamine

```bash
cd backend && python -m pytest tests/ -v
```

Täpsem runbook: [`docs/runbook.md`](docs/runbook.md).

---

## Arhitektuur (Ports & Adapters)

Lokaalselt käivitatav modulaarne monoliit. Tuumloogika on I/O-st lahutatud **portide** kaudu.

```
backend/
    run_adapter.py                   # CLI sisenemispunkt (argparse → wiring)

    domain/                          # puhas äriloogika, ei tee I/O-d
        mapping/c01_raw_to_sv.py     #   RAW → SV kaardistus (C-01)
        projections/c02_sv_to_ml.py  #   SV → ML projektsioon (C-02)
        projections/c03_sv_to_llm.py #   SV → LLM kontekst (C-03)
        rules/invariants_r01.py      #   invariandid + dedupe (R-01)
        report/models.py             #   Issue, RunFlag, CollectedRunReport
        report/ops.py                #   outcome, counts, by_severity

    ports/                           # abstraktsed liidesed (ei I/O, ei Path)
        dataset_port.py              #   sisendi lugemine
        output_port.py               #   artefaktide kirjutamine
        spec_port.py                 #   skeemid, lepingud, profiilid
        clock_port.py                #   aeg + run ID (determinism)

    application/                     # orkestreerimine, räägib ainult portidega
        pipeline.py                  #   7-etapiline pipeline (run_pipeline)

    entrypoints/                     # driving-adapter: portide kokkuühendamine
        wiring_fs.py                 #   FS-adapterid + kell → run_pipeline

    adapters/
        fs/                          # failisüsteemi I/O teostused
            dataset_fs.py            #     datasets/ lugemine
            output_fs.py             #     run folder + failide kirjutamine
            spec_fs.py               #     spec/ laadimine
        system/                      # tootmise adapterid
            clock_real.py            #     RealClock (süsteemiaeg + uuid4)
        testing/                     # testide adapterid
            clock_fixed.py           #     FixedClock (deterministlik kell)

    tests/                           # testid (vt allpool)
```

**Importimisreegel:** `domain` → ei impordi `adapters`, `ports`, `pathlib`, `os`.
`application` → impordib `domain` + `ports`, ei tee I/O-d. `adapters` → teostavad portide liideseid (duck typing).

Täpsem arhitektuurikirjeldus: [`docs/ARHITEKTUUR.md`](docs/ARHITEKTUUR.md).

---

## Determinism ja kell

Adapter pipeline kasutab **kella** (`ClockPort`) kahe asja jaoks:
1. **`now_utc()`** — ISO 8601 UTC ajatempel (nt `"2026-02-24T14:30:00Z"`), mis salvestatakse SV meta, koondraport ja LLM kontekst metaandmetesse ning kasutatakse väljundkausta nimetamiseks.
2. **`new_run_id()`** — unikaalne jooksutunnus (nt `"3f8a1c2b9d04"`).

### Kella teostused

| Klass | Asukoht | Kasutus |
|-------|---------|---------|
| `RealClock` | `adapters/system/clock_real.py` | **Tootmine**: `datetime.now(timezone.utc)` + `uuid.uuid4()` |
| `FixedClock` | `adapters/testing/clock_fixed.py` | **Integratsioonitestid**: fikseeritud ajatempel + run_id |
| `FixedClock` | `tests/fakes/fixed_clock.py` | **Unit-testid**: sama loogika, vaikeväärustega |

### Kuidas determinism tagatakse

- **Tuum (`domain/`)** ei kutsu kunagi `datetime.now()` ega `uuid`. Kella väärtused edastatakse tuumale lihtsate stringidena (`run_id`, `created_at_utc`).
- **SV sisu, ML projektsioon ja LLM kontekst** on determineeritud sisenditest — kellaaeg mõjutab ainult metaandmeid (`meta.run_id`, `meta.created_at_utc`).
- **Testides** süstitakse `FixedClock`, mis tagastab alati sama ajatempli ja run_id → väljundfailid on baidipõhiselt identsed jooksude vahel.
- **Tootmises** süstitakse `RealClock`, mis annab igale jooksule unikaalse ajatempli ja ID.

### ISO 8601 formaat

Kogu projektis kasutatakse ühtset ajatempli formaati, mis on defineeritud ühes kohas:

```python
# adapters/system/clock_real.py
ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"   # nt "2026-02-24T14:30:00Z"
```

---

## Spetsifikatsioonid

Kogu normatiivne käitumine on versioonitud `spec/` kataloogis:

| Tüüp | Identifikaator | Kirjeldus |
|------|----------------|-----------|
| Skeem | S-00A/B/C | RAW sisendi valideerimine (accounts, transactions, standing orders) |
| Skeem | S-01 | Standardiseeritud vaheesituse (SV) skeem |
| Skeem | S-03 | LLM konteksti skeem |
| Skeem | S-05 | Koondraporti skeem |
| Leping | C-01 | RAW → SV kaardistusreeglid |
| Leping | C-02 | SV → ML projektsioon |
| Leping | C-03 | SV → LLM kontekst |
| Reeglistik | R-01 | Invariandid (INV-01..INV-09) + dedupe |

Täpsem spetsifikatsioonide indeks: [`docs/SPETSIFIKATSIOONID.md`](docs/SPETSIFIKATSIOONID.md).

---

## Osaline õnnestumine ja outcome

Pipeline lõpptulem (outcome) on üks kolmest:

| Outcome | Tähendus |
|---------|----------|
| `SUCCESS` | Vigu ei esinenud. INFO-tasemel run_flags võivad esineda. |
| `PARTIAL_SUCCESS` | Esineb WARN/ERROR-tasemel probleeme, kuid fail-gate lävend ei ületatud. |
| `FAIL` | Fail-gate käivitus: ERROR-tasemel drop'ide osakaal ületas lävendi (vaikimisi 5%). |

Fail-gate konfiguratsioon on profiilis `spec/profiles/default.yaml`:
- `run_policy.partial_success_policy.fail_on.any_severity` — minimaalne tõsidus (vaikimisi `ERROR`)
- `run_policy.partial_success_policy.fail_on.ratio_over_records` — drop'ide osakaal (vaikimisi `0.05`)

---

## Dokumentatsioon

| Dokument | Kirjeldus |
|----------|-----------|
| [`docs/ARHITEKTUUR.md`](docs/ARHITEKTUUR.md) | Ports & Adapters arhitektuur, pipeline, failipuu |
| [`docs/ARENDUSLOGI.md`](docs/ARENDUSLOGI.md) | Tehtud otsused, valideerimisparandused, lõhed |
| [`docs/TESTIMINE.md`](docs/TESTIMINE.md) | Testiklassid, käivitamisjuhised |
| [`docs/SPETSIFIKATSIOONID.md`](docs/SPETSIFIKATSIOONID.md) | Skeemide, lepingute ja reeglistike indeks |
| [`docs/runbook.md`](docs/runbook.md) | Operatiivsed käivitamiskäsud |

---

## Testistrateegia

```
backend/tests/
    unit/
        test_pipeline_with_fakes.py  # pipeline läbi fake-portide (mälus, I/O-vaba)
        test_import_boundaries.py    # domain ei impordi keelatud mooduleid
    fakes/                           # in-memory port-teostused testidele
        fake_dataset_port.py
        fake_output_port.py
        fake_spec_port.py
        fixed_clock.py               # FixedClock (vaikeväärustega unit-testidele)
    tests.py                         # integratsioonitestid (FS + tmp_path)
```

**Unit-testid** (`unit/`) kasutavad fake-porte — `FakeDatasetPort`, `FakeOutputPort`, `FakeSpecPort`, `FixedClock`.
Pipeline jookseb täielikult mälus, failisüsteemi ei puudutata. Testivad äriloogikat: kaardistus, invariandid, projektsioonid, outcome.

**Integratsioonitestid** (`tests.py`) kasutavad päris FS-adaptereid läbi `entrypoints/wiring_fs.py`.
Kellaadapterina süstitakse `FixedClock` (fikseeritud ajatempel + run_id).
Väljund kirjutatakse `tmp_path` kausta (pytest fixture). Testivad end-to-end voo: sisend → SV → ML/LLM → koondraport → skeemivalideerimine.

**Determinismitest** (`TestDeterminism`) käivitab pipeline kaks korda sama fikseeritud kellaga ja kontrollib, et kõik väljundfailid on identsed.

**Arhitektuuritestid** tagavad kihistuse: `test_import_boundaries.py` skaneerib `domain/` importe AST-ga.

Käivitamine:

```bash
cd backend && python -m pytest tests/ -v
```

---

## Reprodutseerimise juhend

Sammhaaval juhend pipeline tulemuste reprodutseerimiseks. Täpsem LaTeX-versioon: [`docs/lisa_reprodutseerimise_juhend.tex`](docs/lisa_reprodutseerimise_juhend.tex).

### Eeldused

- Python ≥ 3.11
- Sõltuvused: `jsonschema ≥ 4.20.0`, `PyYAML ≥ 6.0`
- API-võtmeid ega välisandmeid **ei vajata** — andmed on hoidlas (`datasets/`)

### Sammud

1. **Klooni ja fikseeri versioon**
   ```bash
   git clone https://github.com/KerstiM/adapter.git
   cd adapter
   git checkout 653ceea9d735904b3ac4f1dd6a8b7c6579cff7b8
   ```

2. **Paigalda sõltuvused**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. **Käivita pipeline**
   ```bash
   python backend/run_adapter.py --data D1 --out backend/out
   ```

4. **Käivita testid ja SLI/SLO valideerimine**
   ```bash
   cd backend && python -m pytest tests/ -v
   ```

5. **Täielik QA (golden-võrdlus + determinism)**
   ```bash
   python scripts/qa/run_full_qa.py
   ```

### Oodatavad väljundid

- Artefaktid: `backend/out/<ajatempel>_<run_id>/` — `sv.json`, `report.json`, `projections/ml_v1.csv`, `projections/llm_context_v1.json`
- Raport kuvab `outcome` (SUCCESS / PARTIAL_SUCCESS / FAIL) ja SLI-1 kuni SLI-6 täituvust
- Golden-võrdlus: `scripts/qa/verify_goldens.py` kontrollib SHA-256 kontrollsummasid `frozen/v1.0.0/golden/` vastu

### Tõrkeotsing

- **`ModuleNotFoundError`**: sõltuvused puuduvad → `pip install -r backend/requirements.txt`
- **Golden mismatch**: kontrolli commitit (`git log --oneline -1`) ja et `frozen/` kaust ei ole muudetud
