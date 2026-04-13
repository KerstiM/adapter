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
│  │          run_adapter.py (CLI)                                │  │
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

Lisaks on raportis **mõõdikud/kokkuvõte** (counts, by_severity, stage_log) ja CLI-s kuvatakse ka **stop_reason**.

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
    run_adapter.py                   # CLI entry point (argparse → wiring)

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
        report/ops.py                #   outcome, counts, by_severity

    ports/                           # abstraktsed liidesed (ei I/O, ei Path)
        dataset_port.py              #   sisendi lugemine
        output_port.py               #   artefaktide kirjutamine
        spec_port.py                 #   skeemid, lepingud, profiilid
        clock_port.py                #   aeg + run ID (determinism)

    application/                     # orkestreerimine, räägib ainult portidega
        pipeline.py                  #   8-etapiline pipeline (run_pipeline)

    entrypoints/                     # driving-adapter: portide kokkuühendamine
        wiring_fs.py                 #   FS-adapterid → run_pipeline
        api.py                       #   stdlib HTTP API server (port 5000)

    adapters/fs/                     # failisüsteemi I/O teostused
        dataset_fs.py                #   datasets/ lugemine failisüsteemist
        output_fs.py                 #   run folder + failide kirjutamine
        spec_fs.py                   #   spec/ laadimine failisüsteemist

    adapters/system/                 # tootmise adapterid
        clock_real.py                #   RealClock (datetime.now(utc) + uuid4)

    adapters/testing/                # testide adapterid
        clock_fixed.py               #   FixedClock (deterministlik kell)

    tests/                           # testid (vt docs/TESTIMINE.md)
```

---

## Importimisreegel (sõltuvuspiir)

- **`domain`** → ei impordi `adapters`, `ports`, `pathlib`, `os`. Ainult standardlib (`hashlib`, `decimal`, `datetime`).
- **`application`** → impordib `domain` + `ports`; kasutab ka `jsonschema` valideerimiseks. Ei tee I/O-d.
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
- `projections/llm_llama3.txt` / `llm_mistral.txt` / `llm_qwen.txt` — LLM promptimallid
- `projections/stats_v1.json` — statistika (kui profiil lubab C-05 `extra_projections` kaudu)
- `projections/monthly_balance_v1.json` — kuubilanss (kui profiil lubab C-06 `extra_projections` kaudu)

---

## Portid: liidesed, mitte teostus

- `DatasetPort`: `read_accounts()`, `list_transaction_reports()`, `read_transactions_report(name)`, `read_standing_orders_optional()`
- `SpecPort`: `load_profile(profile_id)`, `load_schema(id)`, `load_contract(id)`, `load_ruleset(id)`
- `OutputPort`: `init_run_folder(run_id, created_at_utc)`, `write_sv(bundle)`, `write_ml(rows)`, `write_llm(context)`, `write_report(report)`, `write_ml_model(output, model_suffix)`, `write_llm_model(output, model_suffix)`, `write_extra_projection(data, filename)`
- `ClockPort`: `now_utc()`, `new_run_id()`

---

## Kogutud raport = esmaklassiline artefakt

Raport ei ole "kõrvalprodukt", vaid **põhiartefakt**, mille põhjal tehakse outcome otsus.

- `domain/report/` — tüübid (`Issue`, `Severity`, `RunFlag`, `DropDetail`, `CollectedRunReport`) + abifunktsioonid.
- `application/pipeline.py` — pipeline etapid tagastavad tulemuse + raporti sündmused.
