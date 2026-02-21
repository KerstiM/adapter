# Variant A (Target): lokaalselt käivitatav modulaarne monoliit (Ports & Adapters)

Staatus: **Target**. Current implementation: **may differ**.

**Variant A** on lokaalselt käivitatav **modulaarne monoliit**, kus andmetöötluse tuum (standardiseerimine + reeglid + projektsioonid) on **I/O-st eraldatav** Ports & Adapters vaimus. Töötlus toimub **sammupõhise torustikuna (pipeline)** ning tulemus on alati **kogutud raport** koos stabiilsete artefaktidega.

Operatiivsed käsud ja käivitamisnäited on eraldi runbook’is: [`docs/runbook.md`](docs/runbook.md).

## Põhimõtted

- **Local-first / no-egress**: käivitub lokaalselt; väliseid teenuseid ei eelda.
- **Determinism**: sama sisend → sama SV ja projektsioonid (võimaldab testimist ja reprodutseeritavust).
- **Loogika vs I/O lahutus**:
  - tuumloogika: valideerimine, kaardistus, invariandid, projektsioonid
  - I/O: failisüsteemi lugemine/kirjutamine, CLI argumendid, output kaustad
- **Kogutud raport**: vead/hoiatused ei “kao logisse”, vaid lähevad struktureeritud raportisse.

## Sisend ja väljund (kõrgtasemel)

- Sisend on dataset-kaust Berlin AIS JSON failidega; *standing orders* on valikuline.
- Väljund on SV + projektsioonid + raport eraldi jooksu-kaustas.

## Pipeline etapid (7 sammu)

1. Sisendi lugemine (dataset → sisendobjektid)
2. RAW skeemivalideerimine
3. RAW → SV standardiseerimine (kaardistus)
4. SV skeemivalideerimine
5. Invariantide kontroll (võib tekitada drop’e)
6. Projektsioonid (ML CSV + LLM context)
7. Artefaktide kirjutamine + raporti koostamine + outcome otsus

## Veamudel ja raporti sisu

Raport ja kokkuvõte eristavad kolm tüüpi infot:

- **issues**: reeglina *kirje-põhised* probleemid (skeem/reegel), severity’ga INFO/WARN/ERROR ja viidetega (nt account_id, record_id, field_path, source).
- **run_flags**: *jooksu-põhised* markerid (nt “kasutati fallback’i”, “download-only tuvastus”), severity’ga.
- **dropped_details**: selgitus, miks konkreetne sisendkirje ära jäeti (drop_reason + allikas).

Lisaks on raportis **mõõdikud/kokkuvõte** (counts, by_severity, stage_log) ja CLI-s kuvatakse ka **stop_reason**.

## Outcome semantika

Outcome väärtused on: **SUCCESS**, **PARTIAL_SUCCESS**, **FAIL**.

- **FAIL**: kui *fail-gate* tingimus käivitub.
  - **Konfiguratsiooninõue (target):** fail-gate peab olema kirjeldatud profiilis `spec/profiles/*.yaml` ja vormistatud `run_policy.partial_success_policy.fail_on` all.
  - **Planned default (kui poliitika puudub):** `any_severity = ERROR` ja `ratio_over_records = 0.05`.
  - **Definitsioon (planned default):** `records` = kõik sisendtehingud kokku (Berlin AIS `booked + pending + information` kirjete arv; mitme konto korral summeeritult).
  - Märkus: Berlin AIS `transactions.information` kirjeid võib prototüübis ignoreerida; nende map-fail’ide omissioone ei arvestata fail-gate drop ratio sees.
- **PARTIAL_SUCCESS**: kui
  - esineb ERROR-e, kuid drop ratio jääb alla lävendi, või
  - esineb WARN-e ja/või run_flags (WARN/ERROR).
- **SUCCESS**: kui
  - fail-gate ei käivitu,
  - ei esine WARN/ERROR issues (ega muid WARN/ERROR sündmusi raportis),
  - INFO-tasemel run_flags võivad esineda.

## Stabiilsed artefaktid (leping)

- `sv.json` (SVBundle)
- `projections/ml_v1.csv` (ML projektsioon)
- `projections/llm_context_v1.json` (LLM kontekst)
- `report.json` (kogutud raport)

## Testimisstrateegia

- **Unit**: puhtad reeglid ja determinism (nt normaliseerimine, ID tuletus).
- **Contract**: sisendi/väljundi skeemivalideerimine (spec/schemas).
- **E2E**: kõik datasetid läbi lasta ja valideerida artefaktid; võrrelda outcome ootustega.

## Lõhed / TODO (target → current)

- fail-gate reeglid profiilis (konf peab olema olemas ja üheselt mõistetav)
- run_flags severity ühtlustus
- stop_reason/stage_log olemasolu ja skeem
- E2E validaator kinnitab kõik artefaktid

## Target failipuu (Ports & Adapters + pipeline + collected report)

Allpool on **soovituslik sihtstruktuur**, mis teeb Variant A piirid failipuus nähtavaks. See on modulaarne monoliit: üks deployable/runtime, kuid sisemiselt kihistatud.

```text
adapter/
  backend/
    cli/
      run_adapter.py            # CLI: argumentide parsimine + use-case käivitamine
    application/
      pipeline.py               # pipeline orkestreerimine (puhtad sammud)
      outcome_policy.py         # SUCCESS/PARTIAL_SUCCESS/FAIL otsus (ainult report + policy)
      report_builder.py         # stage_log + metrika + outcome input (report-first)
      validation.py             # skeemivalideerimine prototüübis (jsonschema, 1 teostus)
    domain/
      # Märkus: ära lase domain/models.py paisuda; jaota alammooduliteks
      sv/
        models.py               # SVBundle, SVTransaction, Account
      projections/
        models.py               # MLProjectionRow, LLMContext
        c02_sv_to_ml.py         # leping C-02 (SV -> ML)
        c03_sv_to_llm.py        # leping C-03 (SV -> LLM context)
      raw/
        models.py               # (valikuline) RAW sisendi tüübid, kui tekib vajadus
      rules/
        invariants_r01.py       # invariantide rakendus (R-01)
      mapping/
        c01_raw_to_sv.py        # leping C-01
      report/
        models.py               # Issue, Severity, RunFlag, DropDetail, CollectedRunReport
        ops.py                  # add_issue, add_flag, by_severity, counts helpers
    ports/
      spec_port.py              # spec (schemas/contracts/rulesets/profile) – abstraktsioon
      dataset_port.py           # RAW sisend – abstraktsioon
      output_port.py            # artefaktide kirjutamine – abstraktsioon
      clock_port.py             # aeg/ID (determinism testides)
    adapters/
      fs/                       # ainult failisüsteemi adapterid
        spec_fs.py              # spec/ laadimine failisüsteemist
        dataset_fs.py           # datasets/ lugemine failisüsteemist
        output_fs.py            # run folder + failide kirjutamine
    tests/
      unit/
      contract/
      e2e/
      regression/
        golden/                 # golden/regressioonitestid determinismi tõestamiseks
  spec/
  datasets/
  scripts/
  docs/
    plans/
```

Klikitavus (eesmärk):
- Application kiht ei tea failisüsteemi teekondi; ta räägib ainult portidega.
- Domain kiht on puhas loogika (ei tee I/O-d).
- Adapters/fs on ainus koht, kus kasutatakse `Path`, avatakse faile ja kirjutatakse run folder.

## Importimisreegel (Ports & Adapters = päris sõltuvuspiir)

See on Variant A võttereegel: **koodil peab olema üks suund sõltuvustes**.

Lubatud sõltuvused:

- `domain` → **ei impordi** midagi “väljast” (ei `cli`, ei `adapters`, ei failisüsteemi, ei keskkonnamuutujaid).
- `application` → impordib `domain` + `ports`.
- `application` → ei impordi I/O teeke (nt `pathlib`, `os`, `pandas`, `requests`) ega tee failivõrgu/FS I/O.
  - Erand prototüübis: `application/validation.py` võib kasutada ühte “pure” valideerimismootorit (nt `jsonschema`), sest see ei ole I/O.
- `ports` → ainult liidesed/tüübid (ei I/O, ei `Path`).
- `adapters` → impordib `ports` + 3rd-party I/O teeke (nt pathlib, pandas) ning teeb päris I/O.
- `cli` → impordib `application` ja valib, milliseid adaptereid kasutada.

Praktiline test-soovitus (hilisemaks koodi refaktoriks): lisa test, mis kontrollib, et `domain` ei impordi keelatud mooduleid (nt `pathlib`, `os`, `requests`) ega `backend.adapters.*` pakette.

## Collected report = esmaklassiline artefakt

Target’is ei ole raport “kõrvalprodukt”, vaid **põhiartefakt**, mille põhjal tehakse outcome otsus.

Soovituslik jaotus (target):

- `domain/report/`:
  - tüübid: `Issue`, `Severity`, `RunFlag`, `DropDetail`, `CollectedRunReport`
  - abifunktsioonid: add_issue, by_severity, koonda counts
- `application/report_builder.py`:
  - koondab stage_log’i
  - arvutab metrika
  - valmistab ette “outcome input” (policy + report summary)
- `application/outcome_policy.py`:
  - otsustab SUCCESS/PARTIAL/FAIL **ainult reporti + policy** põhjal

Eesmärk: pipeline etapid tagastavad **tulemuse + report events**, mitte ei kirjuta ise logi.

## Pipeline orkestreerimine application-kihis (puhtad sammud)

Target’is on pipeline application-kihis eraldi nähtav jaotusega “puhasteks sammudeks”, kus I/O on portide taga.

Soovitus: [`backend/application/pipeline.py`](backend/application/pipeline.py) sisaldab ainult orkestreerimist:

- read_raw
- validate_raw
- map_to_sv
- validate_sv
- check_invariants
- project
- write_outputs + finalize_report/outcome

Iga samm:

- saab sisendiks andmestruktuurid
- tagastab (a) uue andmestruktuuri/artefaktid (b) reporti sündmused
- ei tee I/O (see jääb adapteritesse)

## Ports: liidesed, mitte teostus

Portide mõte on, et application räägib abstraktsiooniga (mitte kaustade/failide path’idega). Näidiskuju (target):

- `DatasetPort`: `read_accounts()`, `read_transactions()`, `read_standing_orders_optional()`
- `SpecPort`: `load_schema(id)`, `load_contract(id)`, `load_ruleset(id)`, `load_profile(profile_id)`
- `OutputPort`: `write_sv(bundle)`, `write_projection_ml(rows)`, `write_llm_context(ctx)`, `write_report(report)`
- `ClockPort`: `now_utc()`, `new_run_id()`

**Policy allikas (tee üheselt selgeks):**

- `SpecPort.load_profile()` tagastab *domain model*’i (nt `RunPolicy`), mis sisaldab fail-gate/threshold reegleid.
- `RunPolicy` laadimine (YAML → `RunPolicy`) on adapteri vastutus; application näeb ainult valmis struktuuri läbi SpecPort’i.
- [`outcome_policy.py`](backend/application/outcome_policy.py) kasutab ainult `RunPolicy + report` kombinatsiooni.

**Valideerimine (S-00*, S-01) prototüübis (target):**

- Domain ei tee JSON Schema valideerimist.
- Prototüübis on skeemivalideerimine **application-kihi vastutus** (vt `application/validation.py`) ja kasutab üht konkreetset validaatorit (nt `jsonschema`).
- Prototüübis **ei eelda ega luba** validaatori vahetatavust eraldi pordi kaudu.

Miks validaator pole eraldi port (2–4 lauset):

Prototüübis puudub realistlik vajadus skeemivalidaatorit vahetada ning pordi lisamine tekitaks lisakihte ilma selge kasuta. Ühe teostuse kasutamine hoiab pipeline’i loetavamana ja vähendab dependency-injection keerukust. Kui hiljem tekib päris nõue validaatori vahetuseks (nt mitme skeemimootori tugi), saab `ValidationPort` lisada eraldi “future/optional” sammuna.

Oluline: port **ei kasuta** `Path` ega “tea kaustadest”. Path-resolve on CLI-s või adapteris, mitte domainis.

## Adapterid: üks adapter = üks vastutus

Target’is on üks adapterifail ühe I/O vastutuse jaoks:

- `adapters/fs/spec_fs.py` ainult spec’iga seotud load/resolve
- `adapters/fs/dataset_fs.py` ainult dataset sisendi lugemine
- `adapters/fs/output_fs.py` ainult run folder + kirjutamine

Reegel: ära tee ühte faili, kus on “natuke load_profile + natuke validate + natuke write”.

## Domain: eralda lepingud ja reeglid

Domaini sees on eraldi:

- `domain/mapping/c01_raw_to_sv.py`: saab dictid ja annab SV struktuuri; ei loe faile
- `domain/projections/*`: saab SV ja annab väljundi struktuurid (nt list rows)
- `domain/rules/invariants_r01.py`: tagastab drop events reportile, mitte ei drop’i “vaikides”

Eesmärk: domain on testitav puhtalt Python objektidega.

## Testid: seo testid arhitektuuriga

`backend/tests/` jaotus (target):

- `unit/`: testib `domain` (mapping, invariants, projections) ilma failideta
- `contract/`: valideerib, et sisend/väljund vastab `spec/schemas` ja lepingutele
- `e2e/`: jooksutab `application` pipeline’i päris adapteritega `datasets/` kaustast
- `regression/` või `e2e/golden/`: golden/regressioonitestid, mis kinnitavad determinismi (sama sisend → sama väljund)

Range variant: unit-testid ei tohi importida `adapters`.

## Dokid: arhitektuur vs runbook

Soovituslik paigutus (target):

- Arhitektuur: `docs/architecture/variant_a.md`
- Käivitamine: [`docs/runbook.md`](docs/runbook.md)
- Plaanid/ADR/gap-id: `docs/plans/`

Kui tahad target ja current ausalt koos hoida, lisa "gap list" eraldi faili: [`docs/plans/gaps_variant_a.md`](docs/plans/gaps_variant_a.md).

## Ümbertõstmise kaardistus (current → target)

Siin on *minimaalne* kaardistus, kuidas olemasolev repo loogika jaguneks sihtstruktuuri:

- CLI
  - current: [`backend/run_adapter.py`](backend/run_adapter.py:1)
  - target: [`backend/cli/run_adapter.py`](backend/cli/run_adapter.py:1)
- Pipeline orkestreerimine (use-case)
  - current: (koondatud) [`backend/adapter/pipeline.py`](backend/adapter/pipeline.py:1)
  - target: [`backend/application/pipeline.py`](backend/application/pipeline.py)
- RAW→SV mapping + flatten
  - current: (koondatud) [`backend/adapter/pipeline.py`](backend/adapter/pipeline.py:1)
  - target: [`backend/domain/mapping/c01_raw_to_sv.py`](backend/domain/mapping/c01_raw_to_sv.py:1)
- SV skeemivalideerimine + invariandid
  - current: (koondatud) [`backend/adapter/pipeline.py`](backend/adapter/pipeline.py:1)
  - target: [`backend/domain/rules/invariants_r01.py`](backend/domain/rules/invariants_r01.py:1)
- Projektsioonid (ML + LLM)
  - current: (koondatud) [`backend/adapter/pipeline.py`](backend/adapter/pipeline.py:1)
  - target: [`backend/domain/projections/c02_sv_to_ml.py`](backend/domain/projections/c02_sv_to_ml.py:1) ja [`backend/domain/projections/c03_sv_to_llm.py`](backend/domain/projections/c03_sv_to_llm.py:1)
- Spec profiili/skeemide/lepingute laadimine
  - current: (koondatud) [`backend/adapter/pipeline.py`](backend/adapter/pipeline.py:1) + profiil [`spec/profiles/default.yaml`](spec/profiles/default.yaml:1)
  - target: port [`backend/ports/spec_port.py`](backend/ports/spec_port.py:1) + adapter [`backend/adapters/fs/spec_fs.py`](backend/adapters/fs/spec_fs.py:1)
- Väljundi kirjutamine + run folder
  - current: (koondatud) [`backend/adapter/pipeline.py`](backend/adapter/pipeline.py:1)
  - target: port [`backend/ports/output_port.py`](backend/ports/output_port.py:1) + adapter [`backend/adapters/fs/output_fs.py`](backend/adapters/fs/output_fs.py:1)
- E2E artefaktide validaator
  - current: [`scripts/validate_artifacts.py`](scripts/validate_artifacts.py:1)
  - target: jääb skriptiks; võib hiljem kutsuda sama application kihti läbi portide

## Sammud: kuidas repo ümber teha (ohutu refaktor)

Järjekord, mis hoiab käitumise stabiilsena ja lubab järk-järgult tõsta koodi:

1. Lisa sihtkaustad ja “façade” importid (CLI ja vana pipeline jäävad ajutiselt alles).
2. Tõsta välja puhas loogika (mapping/invariants/projections) domain moodulitesse; kata unit testidega.
3. Eralda I/O fs-adapteritesse (dataset/spec/output) ning defineeri ports-interfeisid.
4. Tee application `run_pipeline` sõltuvaks portidest (dependency injection), mitte `Path`-idest.
5. Lülita CLI kasutama application kihti; vana monoliitne pipeline jääb delegaatoriks või eemaldatakse.
6. Kinnita E2E: jooksuta [`scripts/validate_artifacts.py`](scripts/validate_artifacts.py) ning võrdle vajadusel goldenitega.

