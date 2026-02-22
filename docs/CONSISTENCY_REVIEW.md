# Kooskõla audit: dokumentatsioon ↔ kood

**Kuupäev:** 2026-02-22
**Auditi versioon:** v1
**Hinnang:** PARTIAL — arhitektuur vastab põhiväidetele, kuid dokumentatsiooni detailid on mitmes kohas koodist maha jäänud.

---

## 1. Kokkuvõte

| Kriteerium | Staatus |
|------------|---------|
| Modular monolith | **YES** — üks deploy-ühik, kihid selgelt eraldatud |
| Ports & Adapters | **YES** — portid defineeritud, FS-adapterid olemas, domain puhas |
| Pipeline (7 etappi) | **PARTIAL** — 7 etappi on olemas, kuid dokumentatsiooni ja koodi etapijaotus erineb |
| Collected Report | **YES** — `CollectedRunReport` + `Issue` / `RunFlag` / `DropDetail` olemas ja pipeline täidab neid |
| Importimisreeglid | **YES** — domain ei impordi keelatud mooduleid; application sõltub ainult domain + ports |
| Dokumentatsiooni täpsus | **PARTIAL** — portide meetodinimed valed, README katkine markdown, puuduv link |

---

## 2. Väited ja tõendus (A-plokk)

### 2.1 Väidete tabel

| # | Väide (dokumentatsioonist) | Tõendus koodis | Staatus | Parandussoovitus |
|---|----------------------------|----------------|---------|------------------|
| V-01 | "application sõltub ainult ports + domain" | `application/pipeline.py` impordib ainult `domain.*` ja `ports.*`. Lisaks impordib `jsonschema` (väline teek). | **PARTIAL** | `jsonschema` kasutus on skeemivalideerimine, mis on orkestratsiooni osa — mitte I/O rikkumine. Kuid dokumentatsioon peaks mainima, et application kasutab ka `jsonschema` teeki. |
| V-02 | "domain on puhas loogika, I/O puudub" | Kõik `domain/` failid: ei impordi `os`, `pathlib`, `sys`, `adapters`, `ports`, `application`. Kinnitatud `test_import_boundaries.py` AST-skaneerimisega. | **YES** | — |
| V-03 | "pipeline 7-etapiline" | Koodis `pipeline.py` on 7 etappi: `READ_INPUT`, `STANDARDIZE_TO_SV`, `VALIDATE_SCHEMA`, `CHECK_INVARIANTS`, `PROJECT_ML`, `PROJECT_LLM`, `WRITE_OUTPUTS`. | **PARTIAL** | Dokumentatsioon (ARHITEKTUUR.md) loetleb 7 etappi teise jaotusega: lugemine ja RAW valideerimine on eraldi (etapid 1+2), projektsioonid on koos (etapp 6). Koodis on lugemine+valideerimine üks etapp ja projektsioonid kaks etappi. Vt § 2.2. |
| V-04 | "CollectedRunReport on keskne väljund" | `domain/report/models.py:94` — `CollectedRunReport(TypedDict)` definitsioon olemas. Pipeline täidab seda `report/ops.py:build_report()` kaudu ja kirjutab `out.write_report(report)`. | **YES** | — |
| V-05 | "adapters/fs on driven adapters" | `adapters/fs/dataset_fs.py`, `output_fs.py`, `spec_fs.py`, `clock_impl.py` — kõik teevad I/O-d, ei sisalda domain-loogikat. | **YES** | — |
| V-06 | "entrypoints/ on driving adapter / composition root" | `entrypoints/wiring_fs.py` loob FS-adapterid ja delegeerib `application.pipeline.run_pipeline`'le. | **YES** | — |
| V-07 | "DatasetPort: read_accounts, read_transactions, read_standing_orders_optional" | Tegelikud meetodid: `read_accounts()`, `list_transaction_reports()`, `read_transactions_report(name)`, `read_standing_orders_optional()`. Dokumentatsioon mainib `read_transactions()` asemel on kaks eraldi meetodit. | **NO** | ARHITEKTUUR.md pordi kirjeldus tuleb uuendada. |
| V-08 | "OutputPort: write_sv, write_projection_ml, write_llm_context, write_report" | Tegelikud meetodid: `init_run_folder()`, `write_sv()`, `write_ml()`, `write_llm()`, `write_report()`. Dokumentatsioonis on valed meetodinimed ja `init_run_folder` puudub. | **NO** | ARHITEKTUUR.md pordi kirjeldus tuleb uuendada. |
| V-09 | "SpecPort: load_schema, load_contract, load_ruleset, load_profile" | Vastab koodile: `ports/spec_port.py` sisaldab täpselt need meetodid. | **YES** | — |
| V-10 | "ClockPort: now_utc, new_run_id" | Vastab koodile: `ports/clock_port.py` sisaldab täpselt need meetodid. | **YES** | — |
| V-11 | "adapters impordib ports + I/O teegid" | Adapterid **ei impordi** tegelikult `ports/` mooduleid. Kasutavad Pythoni strukturaalset tüüpimist (Protocol duck typing). Impordivad ainult `json`, `csv`, `pathlib`, `yaml`. | **PARTIAL** | Dokumentatsiooni sõnastust täpsustada: adapterid *teostavad* portide liideseid, kuid ei impordi neid eksplitsiitselt. |
| V-12 | "Deterministlik: sama sisend → sama SV ja projektsioonid" | `ClockPort` võimaldab fikseeritud aja/ID süstimist. `TestDeterminism` testiklass kinnitab identsust. | **YES** | — |
| V-13 | README link `docs/plans/variant-a-project-structure.md` | Fail **ei eksisteeri** — `docs/plans/` kausta pole olemas. | **NO** | Eemaldada katkine link README-st. |
| V-14 | README testide käivitamise koodiplokk | Markdown koodiplokk rida 40 ei ole korrektselt suletud; tekst "Täpsem runbook..." on koodiploki sees. | **NO** | Parandada README.md markdown formaat. |

### 2.2 Pipeline etappide detailne võrdlus

| # | ARHITEKTUUR.md etapp | Koodi etapp (`stage_log` võti) | Vastavus |
|---|----------------------|-------------------------------|----------|
| 1 | Sisendi lugemine (dataset → sisendobjektid) | `READ_INPUT` (sisaldab ka RAW valideerimist) | PARTIAL — kood ühendab lugemise ja valideerimise |
| 2 | RAW skeemivalideerimine | `READ_INPUT` (sama etapp) | PARTIAL — koodis pole eraldi etapp |
| 3 | RAW → SV standardiseerimine (kaardistus) | `STANDARDIZE_TO_SV` | YES |
| 4 | SV skeemivalideerimine | `VALIDATE_SCHEMA` | YES |
| 5 | Invariantide kontroll | `CHECK_INVARIANTS` | YES |
| 6 | Projektsioonid (ML CSV + LLM kontekst) | `PROJECT_ML` + `PROJECT_LLM` | PARTIAL — koodis kaks eraldi etappi |
| 7 | Artefaktide kirjutamine + raport + outcome | `WRITE_OUTPUTS` | YES |

**Kokkuvõte:** mõlemad väidavad 7 etappi, kuid etappide piirid erinevad. Dokumentatsioonis on lugemine ja valideerimine eraldi (1+2) ja projektsioonid koos (6); koodis on lugemine+valideerimine koos (`READ_INPUT`) ja projektsioonid eraldi (`PROJECT_ML` + `PROJECT_LLM`).

---

## 3. Arhitektuurireeglite rikkumised (B-plokk)

### 3.1 Importimisreeglid

| Reegel | Staatus | Rikkumised |
|--------|---------|------------|
| `domain/` ei impordi `adapters/`, `ports/`, `pathlib`, `os`, `sys` | **PASS** | 0 rikkumist. Kinnitatud AST-skaneerimisega (`test_import_boundaries.py`). |
| `application/` ei impordi `adapters/` | **PASS** | 0 rikkumist. `pipeline.py` impordib ainult `domain.*` ja `ports.*`. |
| `application/` ei tee I/O-d | **PASS** | `pipeline.py` ei kasuta `open()`, `Path`, `os` — kogu I/O on delegeeritud portidele. |
| `adapters/` ei sisalda domain-loogikat | **PASS** | Adapterid teevad ainult serialiseerimist/deserialiseerimist (JSON, CSV, YAML). Mapping, invariandid, projektsioonid on `domain/` sees. |
| `entrypoints/` on composition root | **PASS** | `wiring_fs.py` loob adaptereid ja delegeerib pipeline'le. |
| `ports/` sisaldavad ainult liideseid | **PASS** | Kõik port-failid kasutavad `typing.Protocol`, ei sisalda I/O-d ega `Path`-e. |

### 3.2 Reeglite täpsustused

| ID | Prioriteet | Kirjeldus | Fail | Rida |
|----|-----------|-----------|------|------|
| ARCH-01 | **MINOR** | `application/pipeline.py` impordib `jsonschema` (väline teek). Dokumentatsioon väidab "application räägib ainult portidega", kuid `jsonschema` on de facto sõltuvus. See EI OLE I/O rikkumine — skeemivalideerimine on orkestratsiooni loogiline osa. | `backend/application/pipeline.py` | 21 |
| ARCH-02 | **MINOR** | FS-adapterid ei impordi `ports/` mooduleid eksplitsiitselt (duck typing). See on Pythonis täiesti korrektne, kuid erineb dokumentatsiooni väitest "adapters impordib ports". | `backend/adapters/fs/*.py` | — |
| ARCH-03 | **INFO** | `FixedClock` on duplikeeritud kahes kohas: `adapters/fs/clock_impl.py:49` ja `tests/fakes/fixed_clock.py:6`. Kumbki ei impordi teist. Mõlemal on sama API, kuid `tests/fakes` versioonil on vaikeväärtused parameetritele. | `adapters/fs/clock_impl.py`, `tests/fakes/fixed_clock.py` | — |

### 3.3 Kokkuvõte

**BLOCKEReid ei ole.** Arhitektuur on puhas — domain on isoleeritud, application ei tee I/O-d, adapters ei sisalda äriloogikat.

---

## 4. Dokumentatsiooni probleemid (C-plokk)

### 4.1 Puuduv arhitektuuriskeem

`docs/ARHITEKTUUR.md` sisaldab failipuud (kaustade loetelu), kuid **puudub kihtide ja sõltuvuste skeem** (Mermaid, ASCII või muu diagramm), mis näitaks:
- kihid (domain, ports, application, adapters, entrypoints)
- sõltuvuste suund (kes keda impordib)
- I/O piir

**Soovitus:** lisada minimaalne sõltuvusskeem ARHITEKTUUR.md-sse.

### 4.2 Katkine link README-s

`README.md:97` viitab failile `docs/plans/variant-a-project-structure.md`, mis ei eksisteeri.
Kausta `docs/plans/` ei ole repos olemas.

**Prioriteet:** MAJOR — eksitab lugejat.

### 4.3 Katkine markdown README-s

`README.md:40-42` — Bash koodiplokk ei ole korrektselt suletud. Tekst "Täpsem runbook: ..." on kogemata koodiploki sees.

**Prioriteet:** MAJOR — testide käivitamise juhis renderdub valesti.

### 4.4 Portide meetodinimed vale

`docs/ARHITEKTUUR.md:121-123` — kolm porti on kirjeldatud valede meetodinimedega:

| Port | Dokumentatsioonis | Koodis |
|------|-------------------|--------|
| `DatasetPort` | `read_transactions()` | `list_transaction_reports()` + `read_transactions_report(name)` |
| `OutputPort` | `write_projection_ml(rows)` | `write_ml(rows)` |
| `OutputPort` | `write_llm_context(ctx)` | `write_llm(context)` |
| `OutputPort` | *(puudub)* | `init_run_folder(run_id, created_at_utc)` |

**Prioriteet:** MAJOR — portide API kirjeldus ei vasta koodile.

### 4.5 Failipuu duplikatsioon

Failipuu on identses mahus esitatud nii `README.md` (read 51–81) kui ka `docs/ARHITEKTUUR.md` (read 66–96). Kaks koopiat tekitab sünkroniseerimisriski.

**Prioriteet:** MINOR — üks peaks viitama teisele.

### 4.6 Pipeline etappide lahknevus

`docs/ARHITEKTUUR.md` § "Pipeline etapid (7 sammu)" kirjeldab etappe teistsuguse jaotusega kui koodi `stage_log`. Vt § 2.2 ülal.

**Prioriteet:** MINOR — koguarv on sama (7), kuid piirid erinevad.

---

## 5. Tegevusplaan

### Prioriteet: MAJOR

| # | Ülesanne | Fail | Märkus |
|---|----------|------|--------|
| T-01 | Parandada portide meetodinimed ARHITEKTUUR.md-s | `docs/ARHITEKTUUR.md:121-123` | DatasetPort, OutputPort meetodid ei vasta koodile |
| T-02 | Parandada README.md katkine koodiplokk (testide sektsioon) | `README.md:40-42` | Lisada puuduv ` ``` `, eraldada tekst koodist |
| T-03 | Eemaldada katkine link README-st | `README.md:97` | `docs/plans/variant-a-project-structure.md` ei eksisteeri |
| T-04 | Lisada arhitektuuriskeem ARHITEKTUUR.md-sse | `docs/ARHITEKTUUR.md` | Mermaid/ASCII sõltuvusskeem kihtide ja suundadega |

### Prioriteet: MINOR

| # | Ülesanne | Fail | Märkus |
|---|----------|------|--------|
| T-05 | Ühtlustada pipeline etappide kirjeldus koodiga | `docs/ARHITEKTUUR.md:29-35` | Viia etapijaotus vastavusse koodi `stage_log` võtmetega |
| T-06 | Täpsustada adapters → ports sõltuvuse sõnastust | `docs/ARHITEKTUUR.md:105` | "teostavad portide liideseid" vs "impordivad ports" |
| T-07 | Vähendada failipuu duplikatsiooni | `README.md` + `docs/ARHITEKTUUR.md` | README-s kompaktne versioon, link ARHITEKTUUR.md-le |
| T-08 | Mainida application-kihi `jsonschema` sõltuvust | `docs/ARHITEKTUUR.md:103` | Dokumenteerida, et application kasutab jsonschema valideerimiseks |

### Prioriteet: INFO

| # | Ülesanne | Fail | Märkus |
|---|----------|------|--------|
| T-09 | Kaaluda FixedClock duplikatsiooni lahendamist | `adapters/fs/clock_impl.py`, `tests/fakes/fixed_clock.py` | Kaks sõltumatut implementatsiooni; koodi muudatus, mitte selle auditi skoop |

---

## 6. Minimaalne dokikomplekt prototüübi jaoks

### Vajalik (hoida):

| Dokument | Põhjendus |
|----------|-----------|
| `README.md` | Esmane sisenemispunkt: mis see on, kuidas käivitada |
| `docs/ARHITEKTUUR.md` | Kihtide, pipeline ja portide kirjeldus |
| `docs/TESTIMINE.md` | Testistrateegia ja käivitamisjuhised |
| `docs/runbook.md` | Operatiivsed käsud (CLI argumendid, väljund) |

### Kaaluda liitmist/lühendamist:

| Dokument | Soovitus |
|----------|----------|
| `docs/SPETSIFIKATSIOONID.md` | Hea indeks, hoida. Kuid info kattub osaliselt README-ga. |
| `docs/ARENDUSLOGI.md` | Ajalugu, pole igapäevaselt vajalik. Hoida viiteks, kuid mitte prioriteetne. |

### Kustutada / ühendada:

Praegu pole tarbetuid duplikaatfaile. Varasemad duplikaadid (NOTES.md, VALIDATION_REPORT.md) on juba kustutatud (vt ARENDUSLOGI 2026-02-22).

---

## 7. Auditi metoodika

- **Dokumentatsioonifailid:** README.md, docs/ARHITEKTUUR.md, docs/TESTIMINE.md, docs/ARENDUSLOGI.md, docs/SPETSIFIKATSIOONID.md, docs/runbook.md
- **Koodi analüüs:** kõik `backend/` Python-failid (domain, application, ports, adapters, entrypoints, tests)
- **Import-kontrollid:** ripgrep-otsingud keelatud importide tuvastamiseks kihiti
- **Skeemikontroll:** spec/schemas/S-05_collected_report_schema.json olemasolu ja raportimudeli vastavus
- **Testide kontroll:** test_import_boundaries.py, test_no_compat_imports.py, test_pipeline_with_fakes.py, tests.py struktuur ja katvus
