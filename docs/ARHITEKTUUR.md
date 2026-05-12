# Arhitektuur: Variant A (Ports & Adapters)

Lokaalselt käivitatav **modulaarne monoliit**, kus andmetöötluse tuum (standardiseerimine + reeglid + projektsioonid) on **I/O-st eraldatud** Ports & Adapters vaimus. Töötlus toimub **sammupõhise torustikuna (pipeline)** ning tulemus on alati **kogutud raport** koos stabiilsete artefaktidega.

Operatiivsed käsud ja käivitamisnäited: [`docs/runbook.md`](runbook.md).

---

## Põhimõtted

- **Local-first / no-egress**: käivitub lokaalselt; väliseid teenuseid ei eelda.
- **Determinism**: sama sisend → sama SV ja projektsioonid (võimaldab testimist ja reprodutseeritavust).
- **Loogika vs I/O lahutus**:
  - tuumloogika: valideerimine, kaardistus, invariandid, projektsioonid
  - I/O: failisüsteemi lugemine/kirjutamine, CLI argumendid, väljundkaustad
- **Kogutud raport**: vead/hoiatused ei "kao logisse", vaid lähevad struktureeritud raportisse.

---

## Sõltuvusskeem

```
┌──────────────────────────────────────────────────────────────────┐
│                  MODULAARNE MONOLIIT (üks deploy-ühik)            │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    entrypoints/                              │  │
│  │          wiring_fs.py (composition root)                     │  │
│  │          cli_run_adapter.py (CLI)                            │  │
│  │          api.py (HTTP)                                       │  │
│  └──────────┬──────────────────────────────┬───────────────────┘  │
│             │ loob adapterid               │ delegeerib           │
│             ▼                              ▼                      │
│  ┌────────────────────┐         ┌────────────────────────────┐    │
│  │  adapters/         │         │       application/          │    │
│  │  ────────────────  │         │       pipeline.py           │    │
│  │  fs/  (dataset,    │         │                             │    │
│  │       output, spec)│         │  impordib: ports + domain   │    │
│  │  system/clock_real │         │  kasutab ka: jsonschema     │    │
│  │  testing/clock_fix │         └──────┬──────────┬──────────┘    │
│  └────────┬───────────┘                │          │               │
│           │                            │          │               │
│           │ implements                 │ kasutab   │ kutsub        │
│           │ Protocol                   │ liideseid │               │
│           ▼                            ▼          ▼               │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐   │
│  │       ports/        │    │           domain/                │   │
│  │  (Protocol-liidesed)│    │  puhas loogika (standardlib)     │   │
│  │  ─────────────────  │    │  ──────────────────────────────  │   │
│  │  DatasetPort        │    │  mapping/       → C-01           │   │
│  │  OutputPort         │    │  rules/         → R-01           │   │
│  │  SpecPort           │    │  projections/   → C-02..C-06     │   │
│  │  ClockPort          │    │    model_formatters/ → C-04      │   │
│  │                     │    │  report/        → models + ops   │   │
│  └─────────────────────┘    └─────────────────────────────────┘   │
│                                                                    │
│  ports defineerivad liidesed · application kasutab liideseid ·     │
│  adapters pakuvad I/O realiseeringud · domain sisaldab äriloogikat │
└──────────────────────────────────────────────────────────────────┘

Sõltuvuste suund:
  entrypoints  → application, adapters  (composition root)
  application  → domain, ports          (orkestreerib äriloogikat portide kaudu)
  adapters     → ports                  (implements Protocol/ABC)
  domain       → (ainult standardlib: hashlib, decimal, datetime)
  ports        → (ainult typing: Protocol)
```

---

## Sisend ja väljund

- Sisend on dataseti kaust Berlin AIS JSON-failidega; *standing orders* on valikuline.
- Väljund on SV + projektsioonid + raport eraldi jooksukaustas.

---

## Pipeline etapid (8 sammu)

| # | Koodi etapp (`stage_log`) | Kirjeldus |
|---|--------------------------|-----------|
| 1 | `READ_INPUT` | Sisendi lugemine + RAW skeemivalideerimine (S-00A/B/C) |
| 2 | `STANDARDIZE_TO_SV` | RAW → SV standardiseerimine, kaardistus (C-01) |
| 3 | `VALIDATE_SCHEMA` | SV skeemivalideerimine (S-01) |
| 4 | `CHECK_INVARIANTS` | Invariantide kontroll (R-01) + dedupe (INV-09); võib tekitada drop'e |
| 5 | `PROJECT_ML` | ML CSV projektsioon (C-02) |
| 6 | `PROJECT_LLM` | LLM kontekst projektsioon (C-03) |
| 7 | `FORMAT_FOR_MODEL` | Mudeli-spetsiifiline formaatimine (C-04): XGBoost/CatBoost kodeeringud, Llama/Mistral/Qwen prompti mallid. Käivitub ainult siis, kui CLI, API või profiil määrab sihtmudelid. |
| 8 | `WRITE_OUTPUTS` | Artefaktide kirjutamine + raporti koostamine + outcome otsus |

---

## Veamudel ja raporti sisu

Raport eristab kolme tüüpi infot:

- **issues**: kirjepõhised probleemid (skeem/reegel), severity'ga INFO/WARN/ERROR ja viidetega (nt account_id, record_id, field_path, source).
- **run_flags**: jooksupõhised markerid (nt "kasutati fallback'i", "download-only tuvastus"), severity'ga.
- **dropped_details**: selgitus, miks konkreetne sisendkirje ära jäeti (drop_reason + allikas).

Lisaks on raportis **mõõdikud/kokkuvõte** (counts, by_severity, by_severity_issues, stage_log) ja CLI-s kuvatakse ka **stop_reason**.

- **by_severity**: ainult tehingutele kleebitud `flags`-väljade severity-jaotus (tx-flagide loendur).
- **by_severity_issues**: kogu `issues[]` massiivi severity-jaotus — hõlmab ka READ_INPUT, mapping-drop'e ja VALIDATE_SCHEMA issue'eid, mis pole ühegi tehingu külge kleebitud. Summa kattub `len(issues)`-ga ja on CLI-s kuvatav inimloetav indikaator.

---

## Outcome semantika

Väärtused: **SUCCESS**, **PARTIAL_SUCCESS**, **FAIL**.

- **FAIL**: kui *fail-gate* tingimus käivitub.
  - Fail-gate peab olema kirjeldatud profiilis `spec/profiles/*.yaml` (`run_policy.partial_success_policy.fail_on`).
  - Vaikimisi: `any_severity = ERROR` ja `ratio_over_records = 0.05`.
- **PARTIAL_SUCCESS**: esineb ERROR-e (aga drop ratio alla lävendi) või esineb WARN-e / run_flags.
- **SUCCESS**: fail-gate ei käivitu, WARN/ERROR issues puuduvad. INFO-tasemel run_flags võivad esineda.

---

## Failipuu

```text
backend/
    domain/                          # puhas äriloogika, ei tee I/O-d
        mapping/c01_raw_to_sv.py     #   RAW → SV kaardistus (C-01)
        projections/c02_sv_to_ml.py  #   SV → ML projektsioon (C-02)
        projections/c03_sv_to_llm.py #   SV → LLM kontekst (C-03)
        projections/c05_sv_to_stats.py       # statistika projektsioon (C-05)
        projections/c06_sv_to_monthly_balance.py  # kuubilanss (C-06)
        projections/model_formatters/#   C-04 mudelispetsiifilised formaatijad
            _common.py               #     jagatud abifunktsioonid
            llm_templates.py         #     Llama 3 / Mistral / ChatML promptimallid
            ml_encoders.py           #     XGBoost label-encoding, CatBoost native
        rules/invariants_r01.py      #   invariandid + dedupe (R-01)
        report/models.py             #   Issue, RunFlag, CollectedRunReport
        report/ops.py                #   outcome, counts, by_severity, by_severity_issues

    ports/                           # abstraktsed liidesed (ei I/O, ei Path)
        dataset_port.py              #   sisendi lugemine
        output_port.py               #   artefaktide kirjutamine
        spec_port.py                 #   skeemid, lepingud, profiilid
        clock_port.py                #   aeg + run ID (determinism)
        validation_port.py           #   JSON Schema valideerimine

    application/                     # orkestreerimine, räägib ainult portidega
        pipeline.py                  #   8-etapiline pipeline (run_pipeline)

    entrypoints/                     # driving-adapter: väline maailm → pipeline
        cli_run_adapter.py           #   CLI entry point (argparse → wiring)
        wiring_fs.py                 #   FS-adapterid → run_pipeline
        api.py                       #   stdlib HTTP API server (port 8000)

    adapters/fs/                     # failisüsteemi I/O teostused
        dataset_fs.py                #   datasets/ lugemine failisüsteemist
        output_fs.py                 #   run folder + failide kirjutamine
        spec_fs.py                   #   spec/ laadimine failisüsteemist

    adapters/validation/             # valideerimisteostus
        jsonschema_adapter.py        #   JsonSchemaValidationAdapter (jsonschema teek)

    adapters/system/                 # tootmise adapterid
        clock_real.py                #   RealClock (datetime.now(utc) + uuid4)

    adapters/testing/                # testide adapterid
        clock_fixed.py               #   FixedClock (deterministlik kell)

    tests/                           # testid (vt docs/TESTIMINE.md)
```

---

## Importimisreegel (sõltuvuspiir)

- **`domain`** → ei impordi `adapters`, `ports`, `pathlib`, `os`. Ainult standardlib (`hashlib`, `decimal`, `datetime`).
- **`application`** → impordib `domain` + `ports`; valideerimine käib `ValidationPort` kaudu (`jsonschema` teek elab `adapters/validation/`-s). Ei tee I/O-d.
- **`ports`** → ainult liidesed (`Protocol`-klassid); ei I/O, ei `Path`.
- **`adapters`** → teostavad `ports/` Protocol-liideseid (strukturaalne alamtüüpimine); impordivad I/O teegid (`json`, `csv`, `pathlib`, `yaml`).
- **`entrypoints`** → impordib `application` ja `adapters`; composition root (portide liideseid otse ei impordi).

---

## Stabiilsed artefaktid (leping)

- `sv.json` — SVBundle
- `projections/ml_v1.csv` — ML baasprojektsioon
- `projections/llm_context_v1.json` — LLM baaskontekst
- `report.json` — kogutud raport

Mudelispetsiifilised artefaktid (tekivad ainult siis, kui CLI, API või profiil määrab sihtmudelid):

- `projections/ml_xgboost.csv` / `ml_catboost.csv` — ML mudeli-kodeeritud projektsioonid
- `projections/llm_llama3.txt` / `llm_mistral.txt` / `llm_qwen.txt` / `llm_gemma.txt` — LLM promptimallid
- `projections/stats_v1.json` — statistika (kui profiil lisab C-05 `projections` loetellu)
- `projections/monthly_balance_v1.json` — kuubilanss (kui profiil lisab C-06 `projections` loetellu)

---

## Portid: liidesed, mitte teostus

- `DatasetPort`: `read_accounts()`, `list_transaction_reports()`, `read_transactions_report(name)`, `read_standing_orders_optional()`
- `SpecPort`: `load_profile(profile_id)`, `load_schema(id)`, `load_contract(id)`, `load_ruleset(id)`
- `OutputPort`: `init_run_folder(run_id, created_at_utc)`, `write_sv(bundle)`, `write_ml(rows)`, `write_llm(context)`, `write_report(report)`, `write_ml_model(output, model_suffix)`, `write_llm_model(output, model_suffix)`, `write_extra_projection(data, filename)`
- `ClockPort`: `now_utc()`, `new_run_id()`
- `ValidationPort`: `validate(data, schema) → list[dict]` (JSON Schema valideerimine; teostus `adapters/`-s, et `jsonschema` teek tuumast väljas püsiks)

---

## Kogutud raport = esmaklassiline artefakt

Raport ei ole "kõrvalprodukt", vaid **põhiartefakt**, mille põhjal tehakse outcome otsus.

- `domain/report/` — tüübid (`Issue`, `Severity`, `RunFlag`, `DropDetail`, `CollectedRunReport`) + abifunktsioonid.
- `application/pipeline.py` — pipeline etapid tagastavad tulemuse + raporti sündmused.

---

## Laiendatavus (UK3)

Arhitektuur on kavandatud nii, et uusi projektsioone, formaatijaid ja sisendiallikaid saab lisada olemasolevat koodi muutmata (Open/Closed printsiip). Seda tõestavad kuus laiendatavuse tõendit neljal arhitektuuritasandil, mis on testitega kaetud (`tests/unit/test_scalability.py`).

**Ühtne projektsiooniregister.** Kõik projektsioonid (C-02 ML, C-03 LLM, C-05 statistika, C-06 kuubilanss) on registreeritud ühtses `PROJECTION_REGISTRY`-s (`backend/application/projection_registry.py`). Pipeline käivitab need ühe dispatch-tsükliga, mis loeb profiili `projections` loetelu. Nimetusi `"põhi-"` vs `"extra-"` projektsioone ei eksisteeri — kõik on võrdsed kodanikud sama mehhanismi all. Uue projektsiooni lisamine on **lokaalne muudatus**: üks puhas funktsioon + üks kirje registrisse + üks nimi profiili faili.

### Tõend 1 — Projektsiooni laiendatavus (C-05 statistika)

Uus reeglipõhine projektsioon C-05 (statistika) lisati eraldiseisvana. Pipeline'i, porte ega adaptereid ei muudetud. SV vaheesitus on stabiilne laienduspunkt — iga uus projektsioon on puhas funktsioon, mis võtab SVBundle sisendiks.

### Tõend 2 — Formaateri laiendatavus (C-04 dispatch, Gemma)

Uus LLM formaateri moodul Gemma 2 (`domain/projections/model_formatters/llm_gemma.py`) lisati dispatch-tabelisse. Muutused:

- 1 kirje `C-04_model_formatters.yaml` lepingusse (`gemma-2-2b-it` perekonnaga `gemma`)
- 1 import + 1 dict-entry `model_formatters/__init__.py`-s

Pipeline'i, porte, adaptereid ega olemasolevaid formaatijaid ei muudetud. Moodul järgib täpselt sama signatuuri ja mustrit nagu olemasolevad formaatijad (llama3, mistral, chatml). Git-diff on ise tõestus — see näitab, kui väike on muudatus.

### Tõend 3 — Sisendiadapteri laiendatavus (DatasetPort)

Testis defineeritud `SimpleDictDatasetPort` implementatsioon (struktuuriliselt erinev `FakeDatasetPort`-st ja FS-adapterist) läbib pipeline'i end-to-end. Pordi `Protocol` (duck typing) ei sõltu konkreetsest sisemisest struktuurist — piisab meetodite olemasolust.

### Tõend 4 — Projektsiooni laiendatavus, struktuuriliselt uudne kuju (C-06 kuubilanss)

C-06 (kuubilanss) toodab ajaseeria-kujulise cashflow projektsiooni — kuju, mis on struktuuriliselt erinev C-02 (lame), C-03 (kontekstiaken) ja C-05 (lamedad agregaadid) omast. Tõestab, et SV vahekiht toetab ka ajalis-akumulatiivset projektsiooni ilma pipeline'i muutmata. Aktiveeritakse profiili kaudu (`projections: [ml, llm, stats, monthly_balance]`).

### Tõend 5 — Sisendiformaadi laiendatavus (D7 standing orders)

Pipeline käsitleb uut finantsinstrumendi tüüpi (püsikorraldused) ilma pipeline'i tuumkoodi muutmata. Muudatused:

- S-00C skeem (`spec/schemas/S-00C_berlin_standing_orders.schema.json`)
- Valikuline portimeetod `read_standing_orders_optional()` DatasetPort'is
- INFORMATION staatuse tugi kaardistuses (C-01)
- valueDate fallback nextExecutionDate'ist

Pipeline'i orkestreerimiskoodi (`application/pipeline.py`), olemasolevaid projektsioone ega adaptereid ei muudetud. INFORMATION tehingud läbivad SV standardiseerimise, aga jäetakse korrektselt välja ML ja LLM projektsioonidest.

### Tõend 6 — Ühtne dispatch, uue projektsiooni lokaalne lisamine

Fiktiivne uus projektsioon registreeritakse dünaamiliselt `PROJECTION_REGISTRY`-sse ja aktiveeritakse profiili `projections` loetelu kaudu. Pipeline käivitab selle automaatselt ilma ühegi koodimuudatuseta. `TestUnifiedDispatchExtensibility` klassi testid kontrollivad muuhulgas, et pipeline.py ei sisalda konkreetseid projektsiooninimesid — kõik nimed elavad registris, mitte koodis. See kaotab varasema eristuse "põhi-" (C-02/C-03) vs "extra-" (C-05/C-06) projektsioonide vahel.

---

## Piirangud (Threats to validity)

Käesolev jaotis loetleb metodoloogilised piirangud ja väited, mille empiiriline katvus on tahtlikult piiratud. Eesmärk on olla läbipaistev selle suhtes, mida töö tõestab, ja mida mitte.

### Reprodutseeritavus ja korrektsus

- **Golden-kontroll on regressiooni-tuvastus, mitte korrektsuse oraakel.** `frozen/v1.0.0/golden/`-is olevad artefaktid on genereeritud sama pipeline'iga, mida nad valideerivad (`scripts/qa/freeze_goldens.py`). Kui pipeline produtseeriks vale väljundi, talletuks vale vastus goldeniks ja `verify_goldens.py` raporteeriks PASS. Golden-võrdlus tuvastab muutusi jooksude vahel, aga ei ole sõltumatu tõend väljundi tähendusliku õigsuse kohta.
- **Determinism on empiiriline, mitte formaalne tõend.** SLI-4 ja QA skript jooksutavad pipeline'i 5 korda 11 andmestiku peal ja nõuavad baidi-identseid väljundeid. See on tugev empiiriline kinnitus, aga mitte formaalne tõestus, et pipeline on kõikide võimalike sisendite ja keskkondade korral deterministlik.
- **`frozen/v1.0.0/spec.lock.json` on staatiline artefakt.** Fail on repo-s olemas, aga `scripts/qa/build_spec_lock.py` ei ole automaatselt käivitatav ühegi CI-etapi ega entrypoint'i poolt. `report.run.spec_lock_sha256` väli skeemis S-05 on valikuline ega täideta jooksuaegselt. Spec-triivi tuvastamine eeldab käsitsi `build_spec_lock.py` kutsumist ja hashi võrdlust.

### Mõõtmise metoodika

- **SLI-1 on C-01 katvuse manifest, mitte refleksiivne mõõt.** `SLI1_FIELD_COVERAGE` on käsitsi hooldatav sõnastik, kus kõik väärtused on konstruktsioonilt `True`, ja `compute_sli1_coverage()` tagastab alati 1.0 (v.a. sünteetiliste ülekirjutustega unit-testides). Refleksiivne skaneering — skeemis S-01 deklareeritud väljade võrdlus C-01 kaardistuse tegeliku väljundiga — on edasine töö.
- **SLI-5 mõõdab nelja staatilist profiili-konstanti.** `sv_schema_version`, `mapping_version`, `ruleset_version`, `adapter_version` on kõik YAML-ist loetavad versioonistringid, mitte jooksuaegsed audit-jäljed. Valikulised `input_fingerprint`, `output_artifact_hashes`, `spec_lock_sha256` väljad (S-05) pole vaikimisi populaatitud. Seega SLI-5 = 1.0 tõestab ainult seda, et neli versiooni-stringi on kirjas, mitte et jooksu on võimalik täielikult reprodutseerida.
- **SLI-6 viitejõudlus mõõdetakse `FakeOutputPort`-iga.** Ajakulud on domeeniloogika + in-memory hashing + JSON-serialiseerimine, ilma reaalse FS I/O-ta. Reaalse failisüsteemiga on jõudlus ~2 suurusjärku aeglasem (~400 ms vs ~5 ms). 500 ms mediaani SLO D9-l (1000 tx) iseloomustab pipeline'i algoritmilist keerukust, mitte reaalse süsteemi otspunkt-jõudlust.
- **Skaleeruvus on üks mõõtepunkt dataseti kohta, mitte kompleksusanalüüs.** D1 (7 tx), D9 (1000 tx) ja D8 (10 000 tx) jooksu-ajad on mõõdetud ühekordselt (üks warmup + üks mõõdetud jooks) ühe arendaja masina peal. Väide "lineaarne skaleerumine" põhineb kolmel punktil ilma dispersiooni, p95 või O(·) sobitamiseta.

### Andmestikud ja lävendid

- **D10/D11 "reaalsed anonüümistatud" andmestikud on ühe allika omad.** 101 ja 148 tehingut ühe panga ühe kliendi kontojaotustest. Need ei ole populatsiooniliselt esinduslikud ja ei kata pangatoodete variatsiooni (erinevad IBAN-formaadid, transiitkontod, välisvaluutad, korrektsioonikanded).
- **5 % vea-lävend on inseneri hinnang, mitte rikkerežiimi-analüüsist tuletatud.** `partial_success` ja `fail` vahe 5 %-s on valitud mõistliku kokkuleppena (vt `spec/profiles/default.yaml`), mitte kvantitatiivsest analüüsist rikete mõjude kohta. Piir on inclusive (`≥ 5 % → FAIL`), testitud täpselt piiril (5,00 %) ja piiri ümber (4,76 %, 5,26 %).
- **Kvaliteedivärav on parameetriline mehhanism, mitte 5 %-spetsiifiline.** Lävend (`ratio_over_records`) on profiilipõhiselt konfigureeritav (`spec/profiles/*.yaml`); kood ja testid (`backend/tests/sli_slo/test_sli_slo.py::test_gate_boundary_inclusive_semantics`) valideerivad inclusive-`>=` semantikat suvalisel lävendil (1 %, 3 %, 5 %). Töö panus on mehhanism — mitte konkreetse 5 % numbri valideerimine, mis nõuaks tootmismahtude andmeid.

#### Tundlikkusanalüüs: gate'i käitumine erinevatel lävenditel

Andmestikud D12–D14 on sünteetilised süstid vahemikku (0 %, 10 %), mille olemasolu täidab varasema bipolaarsuse — D1–D3, D5, D8–D11 olid 0 % juures (SUCCESS) ja D4 10,26 % juures (FAIL), st lävendi varieerimisel polnud ühelegi olemasolevale andmestikule mõju. D12–D14 võimaldavad demonstreerida, et lävendi muutus tegelikult muudab tulemust:

| Andmestik | error_drop_ratio | @ 1 % | @ 5 % (default) | @ 10 % |
|---|---|---|---|---|
| D1–D3, D5, D8–D11 | 0,00 % | SUCCESS | SUCCESS | SUCCESS |
| D12_synth_partial_low_seed42 | 0,50 % (1/200) | PARTIAL | PARTIAL | PARTIAL |
| D13_synth_partial_mid_seed42 | 3,00 % (3/100) | FAIL (3 ≥ 1) | PARTIAL (3 < 5) | PARTIAL |
| D14_synth_partial_high_seed42 | 7,00 % (7/100) | FAIL | FAIL (7 ≥ 5) | PARTIAL (7 < 10) |
| D4_synth_errors_seed42 | 10,26 % | FAIL | FAIL | FAIL (10,26 ≥ 10) |

D13 ja D14 on **võtmeproovid**: D13 muudab staatust 1 % ja 5 % vahel, D14 muudab staatust 5 % ja 10 % vahel. See näitab, et FAIL ei ole automaatne ja lävendi number on tegelikult otsustav parameeter.

### Arhitektuurilised kontrollid

- **Pordi-piiride test katab ainult `domain/` kihti.** `backend/tests/unit/test_import_boundaries.py` skaneerib `domain/` kausta ja keelab `pathlib`, `os`, `sys`, `uuid`, `random`, `secrets`, `time`, `requests`, `pandas` ning sisemiste pakettide (`adapters`, `application`, `entrypoints`) importi. `application/` kihi I/O-distsipliin on dokumenteeritud konventsioon, aga ei ole automaatselt jõustatud. `datetime` on `domain/`-s lubatud ISO-kuupäeva parsimiseks (`strptime`), aga `datetime.now()` / `.utcnow()` kasutus on keelatud konventsioonina, mitte AST-kontrolliga.

### Standardid ja viited

- **Berlin Group AIS versioon ei ole skeemides fikseeritud.** S-00A/B/C skeemid kasutavad Berlin Group NextGenPSD2 tavakokkulepete pragmaatilist alamhulka (2025. aasta avalike konventsioonide põhjal), aga konkreetne spetsifikatsiooni versioon (nt v1.3.13) ei ole skeemide `title` ega `$comment` väljades kirjas. ISO 20022 element-nimede tabel puudub C-01 lepingust. See on teadlik scope-piirang: töö eesmärk oli demonstreerida standardiseerimise ja reeglistiku arhitektuuri, mitte implementeerida täielik Berlin Group AIS klient.

