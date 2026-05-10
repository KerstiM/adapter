# Adapter / standardiseerimiskiht

Prototüüp loeb Berlin Group / PSD2 AIS stiilis sisendfailid ja teisendab need **standardiseeritud vaheesituseks (SV)**.
SV põhjal tuletatakse deterministlikud **projektsioonid** (ML CSV ja LLM context JSON) ning koostatakse **koondraport**.

Normatiivne käitumine on kirjeldatud `spec/` kataloogi versioonitud skeemide, lepingute ja reeglitega.

## Käivitamine

```bash
# Eeldused: Python 3.11+, sõltuvused paigaldatud
cd backend && pip install -r requirements.txt

# Üks dataset (prefix-match: D1 → D1_synth_valid_small)
python backend/entrypoints/cli_run_adapter.py --data D1 --out backend/out

# Konkreetsete mudelitega
python backend/entrypoints/cli_run_adapter.py --data D1 --target-llm llama3.1-8b-instruct --target-ml xgboost

# Mitu mudelit korraga
python backend/entrypoints/cli_run_adapter.py --data D1 \
  --target-llm llama3.1-8b-instruct mistral-7b-instruct-v0.3 qwen2.5-7b-instruct \
  --target-ml xgboost catboost

# Kohandatud LLM preamble
python backend/entrypoints/cli_run_adapter.py --data D1 --target-llm llama3.1-8b-instruct \
  --llm-preamble "Analüüsi pangatehinguid ja tuvasta anomaaliad."

# Kõik datasetid
for d in datasets/D*; do python backend/entrypoints/cli_run_adapter.py --data "$d" --out backend/out; done
```

CLI argumendid:
- `--data / -d` — dataseti nimi (nt `D1`, `D4`) või kaustatee. Vaikimisi: `D1_synth_valid_small`.
- `--out / -o` — väljundi juurkaust. Vaikimisi: `<repo>/.pipeline_out/` (gitignoreeritud).
- `--profile / -p` — jooksuprofiil (nt `extensions_eval`). Vaikimisi: `default`. Profiil määrab, millised skeemid, lepingud ja reeglistikud on aktiivsed ning milliseid projektsioone pipeline käivitab (`projections` loetelu).
- `--target-llm MODEL [MODEL ...]` — LLM mudel(id), millele genereerida projektsioonid. Valikud: `llama3.1-8b-instruct`, `mistral-7b-instruct-v0.3`, `qwen2.5-7b-instruct`, `gemma-2-2b-it`.
- `--target-ml MODEL [MODEL ...]` — ML mudel(id), millele genereerida projektsioonid. Valikud: `xgboost`, `catboost`.
- `--llm-preamble TEXT` — LLM süsteemne preamble (ülekirjutab profiili seadistuse).

Väljund tekib jooksu-kausta alla:

```
<out>/<timestamp>_<run_id>/
    sv.json                          # kanooniline SVBundle
    report.json                      # koondraport (outcome, issues, counts)
    projections/
        ml_v1.csv                    # ML baasprojektsioon
        llm_context_v1.json          # LLM baaskontekst
        ml_xgboost.csv               # XGBoost-spetsiifiline (kui --target-ml xgboost)
        ml_catboost.csv              # CatBoost-spetsiifiline (kui --target-ml catboost)
        llm_llama3.txt               # Llama 3 prompt (kui --target-llm llama3.1-8b-instruct)
        llm_mistral.txt              # Mistral prompt (kui --target-llm mistral-7b-instruct-v0.3)
        llm_qwen.txt                 # Qwen prompt (kui --target-llm qwen2.5-7b-instruct)
        llm_gemma.txt                # Gemma 2 prompt (kui --target-llm gemma-2-2b-it)
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

## Turvaeeldused ja käitumine

Prototüüp on mõeldud **lokaalseks käivitamiseks** (no-egress, vt lõputöö ptk 1).
Koodi turvapiirid on joondatud selle eeldusega:

- **HTTP API** (`backend/entrypoints/api.py`) seotakse vaikimisi `127.0.0.1:5000` peale, ilma autentimiseta. Hosti ja porti saab override'ida keskkonnamuutujatega `ADAPTER_HTTP_HOST` ja `ADAPTER_HTTP_PORT` — **ärge seadke `0.0.0.0` ilma eelneva autentimis-proxi ja võrgupiiranguteta**, sest `/api/run` vastuses olev `llmPreview.rawContexts` (kui `includeRaw: true` on päringus) sisaldab tehingutasemel andmeid.
- **CORS** on vaikimisi kitsendatud päritoludele `http://localhost:5173` ja `http://127.0.0.1:5173` (Vite dev-server). Allowlist'i saab laiendada keskkonnamuutujaga `ADAPTER_CORS_ORIGINS` (komadega eraldatud loetelu). Wildcard (`*`) ei ole toetatud.
- **`rawContexts` on opt-in**: `POST /api/run` vastus sisaldab täielikke LLM-kontekste ainult siis, kui keha sisaldab `"includeRaw": true`. Ilma selleta näidatakse vaid kokkuvõte (narratiiv, kontoagregatsioon, tippkategooriad) — isikutuvastavad tehingudetailid jäävad kõrvale.
- **Päringu keha** on piiratud 1 MB-le (`MAX_BODY_BYTES`); vigane JSON, puuduv või negatiivne `Content-Length` tagastatakse 400/413-ga enne allokeerimist.
- **Veavastused** ei sisalda Python'i stack trace'i ega erandi teksti; täielik trace läheb ainult serveri stderr'i.
- **LLM preamble** (`--llm-preamble` / `body.llmPreamble`) on käsitletud **untrusted input**'ina: API tasemel on see piiratud 2048 märgile (`MAX_PREAMBLE_CHARS`). Formatter-tasemel eemaldatakse iga toetatud chat-malli kontrolltokenid (`<|eot_id|>`, `[INST]`, `<|im_start|>`, `<start_of_turn>` jm) enne template'i interpoleerimist, et hoida ära downstream-mudeli süsteemvooru kaaperdamist. Sanitiseerimine kehtib kõigile tugetud perekondadele: **llama3, mistral, chatml (Qwen), gemma**.
- **Profiili-põhised faili-teed** (`FsSpecAdapter`) valideeritakse repo juure sisalduvuse vastu (`is_relative_to`), et profile-YAML'i `../../../etc/passwd` tüüpi tee lükataks tagasi `ValueError`-iga.
- **Pre-commit** (`.pre-commit-config.yaml`) sisaldab `gitleaks`-i ja regex-hooki, mis keelab kaardinumbri-viimased-4-numbrit mustri (`..XXXX`) väljaspool D10/D11 datasete ja goldeneid.
- **Jooksu väljund** (`.pipeline_out/` — CLI ja HTTP vaikepath) on gitignoreeritud. **Ära commit'i käsitsi**: väljund võib sisaldada pseudonümiseeritud PII-d sõltuvalt sisendi-datasetist.

Turvaregressioonid on kaetud [`backend/tests/unit/test_api_security.py`](backend/tests/unit/test_api_security.py)-s (API handler, CORS allowlist, `rawContexts` opt-in, preamble pikkuse-kontroll) ja [`backend/tests/unit/test_scalability.py`](backend/tests/unit/test_scalability.py)-s (Gemma chat-token strip).

---

## Arhitektuur (Ports & Adapters)

Lokaalselt käivitatav modulaarne monoliit. Tuumloogika on I/O-st lahutatud **portide** kaudu.

```
backend/
    domain/                          # puhas äriloogika, ei tee I/O-d
        mapping/c01_raw_to_sv.py     #   RAW → SV kaardistus (C-01)
        projections/c02_sv_to_ml.py  #   SV → ML projektsioon (C-02)
        projections/c03_sv_to_llm.py #   SV → LLM kontekst (C-03)
        projections/c05_sv_to_stats.py       # statistika (C-05)
        projections/c06_sv_to_monthly_balance.py  # kuubilanss (C-06)
        projections/model_formatters/#   C-04 mudeliformaatijad
        rules/invariants_r01.py      #   invariandid + dedupe (R-01)
        report/models.py             #   Issue, RunFlag, CollectedRunReport
        report/ops.py                #   outcome, counts, by_severity

    ports/                           # abstraktsed liidesed (ei I/O, ei Path)
        dataset_port.py              #   sisendi lugemine
        output_port.py               #   artefaktide kirjutamine
        spec_port.py                 #   skeemid, lepingud, profiilid
        clock_port.py                #   aeg + run ID (determinism)

    application/                     # orkestreerimine, räägib ainult portidega
        pipeline.py                  #   8-etapiline pipeline (run_pipeline)

    entrypoints/                     # driving-adapter: väline maailm → pipeline
        cli_run_adapter.py           #   CLI sisenemispunkt (argparse → wiring)
        wiring_fs.py                 #   FS-adapterid + kell → run_pipeline
        api.py                       #   stdlib HTTP API server (port 5000)

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

## Mudeli valimine (target models)

Pipeline saab genereerida mudeli-spetsiifilisi projektsioone lisaks baas-CSV ja LLM kontekstile.
Toetatud mudelid on defineeritud lepingus [`spec/contracts/C-04_model_formatters.yaml`](spec/contracts/C-04_model_formatters.yaml).

### Toetatud mudelid

| Tüüp | Mudeli ID | Perekond | Väljundfail |
|------|-----------|----------|-------------|
| LLM | `llama3.1-8b-instruct` | Llama 3 | `llm_llama3.txt` |
| LLM | `mistral-7b-instruct-v0.3` | Mistral | `llm_mistral.txt` |
| LLM | `qwen2.5-7b-instruct` | ChatML | `llm_qwen.txt` |
| LLM | `gemma-2-2b-it` | Gemma 2 (UK3 laiendatavuse tõestus) | `llm_gemma.txt` |
| ML | `xgboost` | XGBoost (numbriline, label-encoded) | `ml_xgboost.csv` |
| ML | `catboost` | CatBoost (kategoriaalsed stringidena) | `ml_catboost.csv` |

### Valikuviisid (prioriteedijärjekorras)

1. **CLI argumendid** — ülekirjutavad profiili seadistuse:
   ```bash
   python backend/entrypoints/cli_run_adapter.py --data D1 --target-llm llama3.1-8b-instruct --target-ml xgboost
   ```

2. **API päring** — `POST /api/run` kehas:
   ```json
   {
     "datasetId": "D1",
     "targetLlm": ["llama3.1-8b-instruct", "mistral-7b-instruct-v0.3"],
     "targetMl": ["xgboost"],
     "llmPreamble": "Analüüsi pangatehinguid."
   }
   ```

3. **Profiili konfiguratsioon** — `spec/profiles/default.yaml`:
   ```yaml
   target_models:
     llm_preamble: "Sa oled finantsanalüüsi assistent."
     llm: ["llama3.1-8b-instruct"]
     ml: ["xgboost"]
   ```

CLI ja API argumendid ülekirjutavad profiili `target_models` sektsiooni (merge-loogika: CLI võtmed asendavad profiili samanimelisi võtmeid).

Kui mudeleid ei ole valitud (ei CLI-s, API-s ega profiilis), genereeritakse ainult baas-projektsioonid (`ml_v1.csv`, `llm_context_v1.json`).

---

## Determinism ja kell

Adapter pipeline kasutab **kella** (`ClockPort`) kahe asja jaoks:
1. **`now_utc()`** — ISO 8601 UTC ajatempel (nt `"2026-02-24T14:30:00Z"`), mis salvestatakse SV meta, koondraport ja LLM kontekst metaandmetesse ning kasutatakse väljundkausta nimetamiseks.
2. **`new_run_id()`** — unikaalne jooksutunnus (nt `"3f8a1c2b9d04"`).

### Kella teostused

| Klass | Asukoht | Kasutus |
|-------|---------|---------|
| `RealClock` | `adapters/system/clock_real.py` | **Tootmine**: `datetime.now(timezone.utc)` + `uuid.uuid4()` |
| `FixedClock` | `adapters/testing/clock_fixed.py` | **Testid**: fikseeritud ajatempel + run_id (kasutatakse nii unit- kui integratsioonitestides) |

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
| Skeem | S-02 | ML projektsiooni rea miinimumveerud ja tüübid |
| Skeem | S-03 | LLM konteksti skeem |
| Skeem | S-05 | Koondraporti skeem |
| Skeem | S-06 | Statistika projektsiooni skeem |
| Skeem | S-07 | Kuubilansi projektsiooni skeem |
| Leping | C-01 | RAW → SV kaardistusreeglid |
| Leping | C-02 | SV → ML projektsioon |
| Leping | C-03 | SV → LLM kontekst |
| Leping | C-04 | Mudelispetsiifilised formaatijad (LLM promptimallid + ML kodeeringud) |
| Leping | C-05 | SV → statistika (kontode ja tehingute kokkuvõtted) |
| Leping | C-06 | SV → kuubilanss (kuu kaupa saldod) |
| Reeglistik | R-01 | Invariandid (INV-01..INV-05, INV-09) + dedupe (INV-09) + QC-1 kvaliteedikontroll |

Täpsem spetsifikatsioonide indeks: [`docs/SPETSIFIKATSIOONID.md`](docs/SPETSIFIKATSIOONID.md).

---

## Osaline õnnestumine ja outcome

Pipeline lõpptulem (outcome) on üks kolmest:

| Outcome | Tähendus |
|---------|----------|
| `SUCCESS` | Vigu ei esinenud. INFO-tasemel run_flags võivad esineda. |
| `PARTIAL_SUCCESS` | Esineb WARN/ERROR-tasemel probleeme, kuid fail-gate lävendit ei saavutatud. |
| `FAIL` | Fail-gate käivitus: ERROR-tasemel drop'ide osakaal on suurem või võrdne lävendiga (vaikimisi `≥ 5%`). |

Fail-gate konfiguratsioon on profiilis `spec/profiles/default.yaml`:
- `run_policy.partial_success_policy.fail_on.any_severity` — minimaalne tõsidus (vaikimisi `ERROR`)
- `run_policy.partial_success_policy.fail_on.ratio_over_records` — drop'ide osakaal (vaikimisi `0.05`)

Värav rakendub **inclusive** semantikaga: `error_drop_ratio >= ratio_over_records → FAIL`. Lävend on profiilipõhiselt konfigureeritav (`spec/profiles/*.yaml`); vaikimisi 5% on prototüübi demonstreerimise jaoks valitud kompromiss, tootmiskasutuses tuleks see kalibreerida ajaloolise ERROR-osakaalu jaotuse vastu.

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
        test_pipeline_with_fakes.py       # pipeline läbi fake-portide (mälus, I/O-vaba)
        test_import_boundaries.py         # domain ei impordi keelatud mooduleid
        test_model_formatters.py          # C-04 mudeliformaatijate testid
        test_pipeline_with_model_target.py # pipeline + mudelisihtmärk end-to-end
        test_scalability.py               # UK3 laiendatavuse tõendid + integratsioon
    fakes/                                # in-memory port-teostused testidele
        fake_dataset_port.py
        fake_output_port.py
        fake_spec_port.py
    sli_slo/
        test_sli_slo.py                   # SLI/SLO metrikate testid (72 testi)
    tests.py                              # integratsioonitestid (FS + tmp_path)
```

**Unit-testid** (`unit/`) kasutavad fake-porte — `FakeDatasetPort`, `FakeOutputPort`, `FakeSpecPort` ja `FixedClock` (asub `adapters/testing/clock_fixed.py`).
Pipeline jookseb täielikult mälus, failisüsteemi ei puudutata. Testivad äriloogikat: kaardistus, invariandid, projektsioonid, mudeliformaatijad, outcome.

**Integratsioonitestid** (`tests.py`) kasutavad päris FS-adaptereid läbi `entrypoints/wiring_fs.py`.
Kellaadapterina süstitakse `FixedClock` (fikseeritud ajatempel + run_id).
Väljund kirjutatakse `tmp_path` kausta (pytest fixture). Testivad end-to-end voo: sisend → SV → ML/LLM → koondraport → skeemivalideerimine.

**Determinismitest** (`TestDeterminism`) käivitab pipeline viis korda sama fikseeritud kellaga ja kontrollib, et kõik väljundfailid on identsed.

**Arhitektuuritestid** tagavad kihistuse: `test_import_boundaries.py` skaneerib `domain/` importe AST-ga.

Käivitamine:

```bash
cd backend && python -m pytest tests/ -v
```

---

## Reprodutseerimise juhend

Sammhaaval juhend pipeline tulemuste reprodutseerimiseks.

### Eeldused

- Python ≥ 3.11
- Sõltuvused: `jsonschema ≥ 4.20.0`, `PyYAML ≥ 6.0`
- API-võtmeid ega välisandmeid **ei vajata** — andmed on hoidlas (`datasets/`)

### Sammud

1. **Klooni ja fikseeri versioon**
   ```bash
   git clone https://github.com/KerstiM/adapter.git
   cd adapter
   git checkout d3f0a1326bb14dd261eaac2f62282d97e673fa39
   ```

2. **Paigalda sõltuvused**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. **Käivita pipeline**
   ```bash
   python backend/entrypoints/cli_run_adapter.py --data D1 --out backend/out
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
- Raport kuvab `outcome` (SUCCESS / PARTIAL_SUCCESS / FAIL) ja SLI/QC metrikaid (SLI-1..SLI-6 + QC-2)
- Golden-võrdlus: `scripts/qa/verify_goldens.py` kontrollib SHA-256 kontrollsummasid `frozen/v1.0.0/golden/` vastu

### Tõrkeotsing

- **`ModuleNotFoundError`**: sõltuvused puuduvad → `pip install -r backend/requirements.txt`
- **Golden mismatch**: kontrolli commitit (`git log --oneline -1`) ja et `frozen/` kaust ei ole muudetud
