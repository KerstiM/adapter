# ID-de sõnastik

Selle faili eesmärk on anda ühe ekraaniga ülevaade repos kasutatavatest identifikaatoritest. Detailsed seosed on `traceability_matrix.csv` ja ristviidete CSV-des.

## Lühinäide: ühe nõude ahel

```
F4 (determinism)
  → QS1 (determinism)
    → SLI4 = 1,0
      → TJ-01 (hash-võrdlus korduskäitustes)
      → TJ-02 (golden-regressioon)
        → tõendus: sv.json, report.json, ml_v1.csv, llm_context_v1.json
        → frozen/v1.1.0/golden/<D*>/*.sha256
          → ADR-01, ADR-03, ADR-04
```

See ahel näitab, kuidas nõue `F4` kulgeb kvaliteedistsenaariumist (QS) mõõdiku (SLI) kaudu testijuhu (TJ) ja konkreetsete tõendusartefaktideni, ning milliste ADR-idega ta on seotud.

## Nõuete tüübid

| ID | Tüüp | Sisu (lühidalt) |
|----|------|-----------------|
| Ä1 | äriline | Laenuriski hindamise tugi ühtlustatud ja võrreldava sisendvooga. |
| Ä2 | äriline | Minimaalne mõju olemasolevatele töövoogudele; vahendus- ja standardiseerimiskiht. |
| Ä3 | äriline | Sisendvoo kvaliteet peab olema mõõdetav ja tõendatav. |
| F1 | funktsionaalne | Sisendandmete standardiseerimine SV-ks ja projektsioonide moodustamine. |
| F2 | funktsionaalne | SV minimaalne ulatus, kui sisendis olemas. |
| F3 | funktsionaalne | Valideerimine ja struktureeritud veakäsitlus; `partial_success` värava tingimustel. |
| F4 | funktsionaalne | Deterministlik teisendus. |
| F5 | funktsionaalne | Andmekao vältimine; äriliselt oluline info ei kao ilma dokumenteeritud erandita. |
| F6 | funktsionaalne | Tuletatud väljad ja projektsioonid on dokumenteeritud, versioonitavad ja korduvkasutatavad. |
| MF1 | kvaliteedi (MF) | Teostatav organisatsiooni standardplatvormil. |
| MF2 | kvaliteedi (MF) | No-egress ja ülekantavus sisekeskkonda. |
| MF3 | kvaliteedi (MF) | Laiendatavus ja skeemievolutsioon minimaalse koodimõjuga. |
| MF4 | kvaliteedi (MF) | Testitavus ja jälgitavus. |
| MF5 | kvaliteedi (MF) | Reprodutseeritavus: samad versioonid → sama tulemus. |
| MF6 | kvaliteedi (MF) | Jõudluse mõistlikkuse kontroll prototüübi kontekstis. |

## Kvaliteedistsenaariumid (QS)

| ID | Stsenaarium |
|----|-------------|
| QS1 | Determinism. |
| QS2 | Laiendatavus / skeemievolutsioon. |
| QS3 | Valideerimine ja veakäsitlus. |
| QS4 | Kontrollitav andmekadu / eemaldatud kirjete selgitus. |
| QS5 | Standardiseerimise kvaliteet / versioonitud väljundid. |
| QS6 | Jõudluse mõistlikkuse kontroll lokaalses prototüübikontekstis. |

## Mõõdikud ja kontrollid (SLI / QC / Gate)

| ID | Sihttase / kirjeldus |
|----|----------------------|
| SLI1 | Prioriteetsete SV-väljade katvus ≥ 0,95 (spetsifikatsioonitaseme näitaja). |
| SLI2 | Valideerimise läbivus ≥ 0,99 puhastel või tootmislaadsetel andmestikel. |
| SLI3 | Invariantide korrektsus ≥ 0,999; kriitilised = 0. |
| SLI4 | Determinism = 1,0 (korduskäitamised annavad identsed väljundid). |
| SLI5 | Auditijälje täielikkus = 1,0 (kõik nõutud metaandmed olemas). |
| SLI6 | Referentsjõudlus: D9 mediaan ≤ 500 ms samas mõõtekeskkonnas (kalibreeritud orientiir, mitte universaalne SLO). |
| QC1 | `INFO`-taseme diagnostika: vastaspoole puudumine. Ei mõjuta staatust. |
| QC2 | Eemaldatud kirjete raporteeritavus = 1,0. |
| Gate | Operatiivne kvaliteedivärav: FAIL, kui `error_drop_ratio ≥ 5%`. |

## Arhitektuuriotsused (ADR)

Täistekst: `docs/ARHITEKTUUR.md` ning lõputöö lisa 9.

| ID | Pealkiri (lühidalt) |
|----|---------------------|
| ADR-01 | Deterministlik väljundpakett (SV + raport + projektsioonid). |
| ADR-02 | Lokaalne CLI/batch, no-egress. |
| ADR-03 | Monoliit portide ja adapteritega (tuum eraldatud I/O-st). |
| ADR-04 | Lineaarne etapiline torustik (pipeline). |
| ADR-05 | SV kui andmeleping; projektsioonid tuletatakse SV-st. |
| ADR-06 | Versioonitud skeemid/reeglid/konf ja käituse pinning. |
| ADR-07 | Kogutud raport + `partial_success` loogika. |
| ADR-08 | Valikuline UI on adapter, mitte osa tuumast. |

## Spetsifikatsioonid

| ID | Tüüp | Asukoht |
|----|------|---------|
| S-00A | skeem (JSON Schema) | `spec/schemas/S-00A_berlin_accounts.schema.json` |
| S-00B | skeem | `spec/schemas/S-00B_berlin_transactions.schema.json` |
| S-00C | skeem | `spec/schemas/S-00C_berlin_standing_orders.schema.json` |
| S-01 | skeem (SV) | `spec/schemas/S-01_sv_schema.json` |
| S-02 | skeem (ML) | `spec/schemas/S-02_ml_projection_schema.json` |
| S-03 | skeem (LLM) | `spec/schemas/S-03_llm_context_schema.json` |
| S-05 | skeem (raport) | `spec/schemas/S-05_collected_report_schema.json` |
| S-06 | skeem (stats) | `spec/schemas/S-06_stats_schema.json` |
| S-07 | skeem (kuubilanss) | `spec/schemas/S-07_monthly_balance_schema.json` |
| C-01 | leping (RAW→SV) | `spec/contracts/C-01_berlin_to_sv.yaml` |
| C-02 | leping (SV→ML) | `spec/contracts/C-02_sv_to_ml.yaml` |
| C-03 | leping (SV→LLM) | `spec/contracts/C-03_sv_to_llm.yaml` |
| C-04 | leping (mudelispetsiifilised formaatijad) | `spec/contracts/C-04_model_formatters.yaml` |
| C-05 | leping (SV→stats) | `spec/contracts/C-05_sv_to_stats.yaml` |
| C-06 | leping (SV→monthly_balance) | `spec/contracts/C-06_sv_to_monthly_balance.yaml` |
| R-01 | reeglistik (invariandid) | `spec/rulesets/R-01_sv_invariants.yaml` |
| error_catalog | reeglistik (veakoodid) | `spec/rulesets/error_catalog.yaml` |
| QC_quality_checks | reeglistik (INFO-kontrollid) | `spec/rulesets/QC_quality_checks.yaml` |
| PROFILE-DEFAULT | profiil | `spec/profiles/default.yaml` |
| PROFILE-EXTENSIONS_EVAL | profiil | `spec/profiles/extensions_eval.yaml` |
| LOCK | versioonide lukustus | `frozen/v1.0.0/spec.lock.json`, `frozen/v1.1.0/spec.lock.json` |
| GOLDEN-MANIFEST | golden SHA-256 | `frozen/v1.0.0/manifest.json`, `frozen/v1.1.0/manifest.json` |

## Andmestikud

Tüübid: **A** = avalik näidis, **S** = sünteetiline (fikseeritud `seed`), **R** = käsitsi de-identifitseeritud pärisandmed.

| ID | Tüüp | Asukoht | Oodatav lõppseisund |
|----|------|---------|---------------------|
| D1 | A | `datasets/D1_synth_valid_small/` | SUCCESS |
| D2 | A | `datasets/D2_synth_mixed_large/` | PARTIAL_SUCCESS (INV-05 WARN) |
| D3 | S | `datasets/D3_synth_valid_seed42/` | SUCCESS |
| D4 | S | `datasets/D4_synth_errors_seed42/` | FAIL (gate) |
| D5 | S | `datasets/D5_synth_edges_seed99/` | SUCCESS |
| D6 | S | `datasets/D6_synth_dupes_seed99/` | PARTIAL_SUCCESS |
| D7 | S | `datasets/D7_standing_orders_seed77/` | PARTIAL_SUCCESS |
| D8 | S | `datasets/D8_load_test_10k_seed88/` | SUCCESS (koormustest) |
| D9 | S | `datasets/D9_synth_perf_seed9/` | SUCCESS (SLI6 referents) |
| D10 | R | `datasets/D10_real_deid_oct16/` | PARTIAL_SUCCESS (INV-05 WARN x77) |
| D11 | R | `datasets/D11_real_deid_2024/` | SUCCESS |

## Testijuhud (TJ)

| ID | Kirjeldus | Peamine tõendusfail |
|----|-----------|---------------------|
| TJ-01 | Korduskäitamise determinism (SLI4 = 1,0; N=5 identset räsi). | `backend/tests/sli_slo/test_sli_slo.py` |
| TJ-02 | Golden-regressioon (SHA-256 võrdlus). | `scripts/qa/verify_goldens.py` |
| TJ-03 | Skeemi-/lepingulevalideerimine (SLI1). | `backend/tests/test_integration_fs.py` |
| TJ-04 | Vigane sisend + partial_success + gate (SLI2, QC2, Gate). | `backend/tests/sli_slo/test_sli_slo.py` |
| TJ-05 | Invariantide kontroll (SLI3, kriitilised = 0). | `backend/tests/unit/test_invariants_r01.py` |
| TJ-06 | Skeemievolutsioon / laiendatavuse stsenaarium (SLI5). | `backend/tests/unit/test_c05_stats.py` |
| TJ-07 | Referentsjõudluse sanity-check (SLI6). | `backend/tests/unit/test_scalability.py` |
| TJ-08 | `extensions_eval` profiili lisaprojektsioonid (SLI5). | `backend/tests/unit/test_c06_monthly_balance.py` |
| TJ-09 | Arhitektuurilise eraldatuse ja turvaeelduste kontroll (Ä2, MF2): tuuma I/O-eraldatus, API turvaeeldused, path-traversal kaitse. | `backend/tests/unit/test_import_boundaries.py`, `backend/tests/unit/test_api_security.py`, `backend/tests/unit/test_spec_fs_path_traversal.py` |
