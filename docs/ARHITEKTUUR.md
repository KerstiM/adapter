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

## Sisend ja väljund

- Sisend on dataseti kaust Berlin AIS JSON-failidega; *standing orders* on valikuline.
- Väljund on SV + projektsioonid + raport eraldi jooksukaustas.

---

## Pipeline etapid (7 sammu)

1. Sisendi lugemine (dataset → sisendobjektid)
2. RAW skeemivalideerimine
3. RAW → SV standardiseerimine (kaardistus)
4. SV skeemivalideerimine
5. Invariantide kontroll (võib tekitada drop'e)
6. Projektsioonid (ML CSV + LLM kontekst)
7. Artefaktide kirjutamine + raporti koostamine + outcome otsus

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

    tests/                           # testid (vt docs/TESTIMINE.md)
```

---

## Importimisreegel (sõltuvuspiir)

- **`domain`** → ei impordi `adapters`, `ports`, `pathlib`, `os`.
- **`application`** → impordib `domain` + `ports`, ei tee I/O-d.
- **`ports`** → ainult liidesed/tüübid (ei I/O, ei `Path`).
- **`adapters`** → impordib `ports` + I/O teegid; teeb päris I/O.
- **`entrypoints/cli`** → impordib `application` ja valib adapterid.

---

## Stabiilsed artefaktid (leping)

- `sv.json` — SVBundle
- `projections/ml_v1.csv` — ML projektsioon
- `projections/llm_context_v1.json` — LLM kontekst
- `report.json` — kogutud raport

---

## Portid: liidesed, mitte teostus

- `DatasetPort`: `read_accounts()`, `read_transactions()`, `read_standing_orders_optional()`
- `SpecPort`: `load_schema(id)`, `load_contract(id)`, `load_ruleset(id)`, `load_profile(profile_id)`
- `OutputPort`: `write_sv(bundle)`, `write_projection_ml(rows)`, `write_llm_context(ctx)`, `write_report(report)`
- `ClockPort`: `now_utc()`, `new_run_id()`

---

## Kogutud raport = esmaklassiline artefakt

Raport ei ole "kõrvalprodukt", vaid **põhiartefakt**, mille põhjal tehakse outcome otsus.

- `domain/report/` — tüübid (`Issue`, `Severity`, `RunFlag`, `DropDetail`, `CollectedRunReport`) + abifunktsioonid.
- `application/pipeline.py` — pipeline etapid tagastavad tulemuse + raporti sündmused.
