# Adapter / standardiseerimiskiht

Prototüüp loeb Berlin Group / PSD2 AIS stiilis sisendfailid ja teisendab need standardiseeritud vaheesituseks (SV).
SV põhjal tuletatakse deterministlikud projektsioonid (ML CSV ja LLM context JSON) ning koostatakse koondraport.

Normatiivne käitumine on kirjeldatud `spec/` kataloogi versioonitud skeemide, lepingute ja reeglitega.

## Käivitamine

```bash
# Eeldused: Python 3.10+, sõltuvused paigaldatud
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

Täpsem käivitusjuhend: [`docs/runbook.md`](docs/runbook.md).

## Testide käivitamine

```bash
cd backend && python -m pytest tests/ -v
```

Täpsem runbook: [`docs/runbook.md`](docs/runbook.md).

---

## Arhitektuur (Ports & Adapters)

Lokaalselt käivitatav modulaarne monoliit. Tuumloogika on I/O-st lahutatud portide kaudu.

```
backend/
    run_adapter.py                   # CLI entry point (argparse → wiring)

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
        wiring_fs.py                 #   FS-adapterid → run_pipeline

    adapters/fs/                     # konkreetsed I/O teostused
        dataset_fs.py                #   datasets/ lugemine failisüsteemist
        output_fs.py                 #   run folder + failide kirjutamine
        spec_fs.py                   #   spec/ laadimine failisüsteemist
        clock_impl.py                #   SystemClock + FixedClock

    tests/                           # testid (vt allpool)
```

**Importimisreegel:** `domain` → ei impordi `adapters`, `ports`, `pathlib`, `os`.
`application` → impordib `domain` + `ports`, ei tee I/O-d. `adapters` → teostavad portide liideseid (duck typing).

Täpsem testistrateegia: [`docs/TESTIMINE.md`](docs/TESTIMINE.md).

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
        fixed_clock.py
    tests.py                         # integratsioonitestid (FS + tmp_path)
    test_no_compat_imports.py        # guard: vana compat-kiht on eemaldatud
```

**Unit-testid** (`unit/`) kasutavad fake-porte — `FakeDatasetPort`, `FakeOutputPort`, `FakeSpecPort`, `FixedClock`.
Pipeline jookseb täielikult mälus, failisüsteemi ei puudutata. Testivad äriloogikat: mapping, invariandid, projektsioonid, outcome.

**Integratsioonitestid** (`tests.py`) kasutavad päris FS-adaptereid läbi `entrypoints/wiring_fs.py`.
Väljund kirjutatakse `tmp_path` kausta (pytest fixture). Testivad end-to-end voo: sisend → SV → ML/LLM → raport → skeemivalideerimine.

**Arhitektuuritestid** tagavad kihistuse: `test_import_boundaries.py` skaneerib `domain/` importe AST-ga;
`test_no_compat_imports.py` kinnitab, et vana `backend/adapter/` compat-kiht on eemaldatud.

Käivitamine:

```bash
cd backend && python -m pytest tests/ -v
```
