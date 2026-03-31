# SLI/SLO testitulemused

**Testifail:** `backend/tests/sli_slo/test_sli_slo.py`
**Käivitamine:** `cd backend && python -m pytest tests/sli_slo/test_sli_slo.py -v`
**Viimane käivitus:** 2026-03-17
**Tulemus: 72/72 läbisid**

---

## SLI/SLO definitsioonid

| # | SLI nimi | Definitsioon | Mõõtetase | SLO sihtmärk |
|---|----------|-------------|-----------|--------------|
| SLI-01 | Skeemikatvus | covered_priority_fields / all_priority_fields | Spetsifikatsioon | ≥ 0.95 |
| SLI-02 | Valideerimise läbivus (standardiseeritud vaheesitusse jõudmise määr) | passed_validation_total / input_records_total | Jooksupõhine | ≥ 0.99 (puhas sisend) |
| SLI-03 | Invariantide täituvus (mapping drops ei kuulu nimetajasse) | invariant_correct_total / invariant_checked_total | Jooksupõhine | ≥ 0.999; critical == 0 |
| SLI-04 | Determinism | identsete väljunditega jooksud / kõik kordusjooksud (N=5) | Mitme jooksu võrdlus | 100 % |
| SLI-05 | Auditijälje täielikkus | olemasolevad nõutud auditiväljad / kõik nõutud auditiväljad | Jooksupõhine | 100 % |
| SLI-06 | Referentsjõudlus | mediaanne töötlusaeg referentsandmestikul (1 proovijooks + 3 mõõdetud) | Eraldi mõõtmine | Informatiivne referentsmõõtmine |
| QC-02| Eemaldatud kirjete raporteeritavus | dropped_details_count / dropped_total | Jooksupõhine | 100 % |
| Gate | Operatiivne kvaliteedivärav | error_drop_ratio < 5 % → PARTIAL_SUCCESS; ≥ 5 % → FAIL | Jooksupõhine | Ei ole SLI |

### Mõõtetasemed ja report.json

- **Jooksupõhised näitajad** (SLI-02, SLI-03, SLI-05, QC-02): report.json metrics sektsioonis või selle aluseks olevatest väljadest arvutatavad.
- **SLI-04 (determinism)**: EI OLE report.json metrics väli. Hinnatakse 5 kordusjooksu alusel.
- **SLI-06 (referentsjõudlus)**: EI OLE report.json metrics väli. Hinnatakse eraldi jõudlusmõõtmise alusel.
- **SLI-01 (skeemikatvus)**: Spetsifikatsioonitaseme näitaja. Kaasatud report.json-i, sest on staatiline ja üheselt arvutatav.

---

## SLI-01 — Skeemikatvus

**SLO:** ≥ 0.95 — C-01 peab katma vähemalt 95 % prioriteetsetest SV väljadest.

**Definitsioon:**

SLI-01 = covered_priority_fields / all_priority_fields

kus:
- `priority_sv_fields_total` = prioriteetsete SV tehinguväljade arv, mis kuuluvad katvuse skoopi
- `covered_priority_sv_fields` = prioriteetsed SV väljad, millele C-01 määrab üheselt kaardistus- või tuletamisloogika
- See on spetsifikatsioonitaseme näitaja, mis põhineb hooldataval katvusdeklaratsioonil (`SLI1_FIELD_COVERAGE` moodulis `domain.report.ops`)
- Näitaja ei sõltu konkreetsest andmestikust ega jooksust

### SLI-01 väljaskoop (17 välja)

| Väli | Kaetud | Kaardistamise allikas |
|------|--------|---------------------|
| `record_id` | Jah | SHA-256 räsi komposiitvõtmest |
| `transaction_id` | Jah | raw `transactionId` |
| `account_id` | Jah | raw konto `resourceId` |
| `status` | Jah | booked/pending/information kategooria |
| `booking_date` | Jah | raw `bookingDate` |
| `value_date` | Jah | raw `valueDate` (fallback-loogikaga) |
| `amount.currency` | Jah | raw `transactionAmount.currency` |
| `amount.raw` | Jah | raw `transactionAmount.amount` |
| `amount.signed` | Jah | tuletatud: absoluutväärtus + suunamärk |
| `amount.abs` | Jah | tuletatud: summa absoluutväärtus |
| `direction` | Jah | tuletatud deebitor/kreeditor/märgi heuristikast |
| `counterparty.role` | Jah | tuletatud suunast |
| `counterparty.name` | Jah | raw `creditorName`/`debtorName` |
| `counterparty.iban` | Jah | raw `creditorAccount`/`debtorAccount` |
| `remittance` | Jah | raw `remittanceInformationUnstructured` |
| `source.input_file` | Jah | C-01 konstrueerib jälgitavuse jaoks |
| `source.input_path` | Jah | C-01 konstrueerib (JSON path avaldis) |

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_sli1_metric_exists_in_report` | SLI-01 metrika on `report.metrics.sli1` all |
| `test_sli1_has_required_keys` | SLI-01 sisaldab kõiki 3 nõutud välja |
| `test_sli1_priority_fields_positive` | `priority_sv_fields_total > 0` |
| `test_sli1_covered_leq_total` | `covered <= total` |
| `test_sli1_ratio_in_unit_interval` | `0 <= ratio <= 1` |
| `test_sli1_baseline_meets_slo` | Praegune baas >= 0.95 |
| `test_sli1_ratio_decreases_when_field_uncovered` | Ühe välja eemaldamine vähendab suhtarvu |
| `test_sli1_in_pipeline_summary` | SLI-01 on ka pipeline'i summary.metrics all |

### Tulemus

```
8/8 PASSED
```

**SLO täidetud: JAH**

---

## Struktuurne väljundi terviklikkus

Need testid kontrollivad, et väljundartefaktid (SV, ML, LLM, raport) sisaldavad
nõutud tipptaseme struktuuri ja võtmeid. Need on kasulikud struktuurse terviklikkuse
kontrollid, kuid EI OLE ametlik SLI-01 metrika.

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_sv_bundle_has_meta` | SV bundle sisaldab `meta` sektsiooni |
| `test_sv_bundle_has_accounts` | SV bundle loetleb töödeldud kontod |
| `test_sv_bundle_has_transactions` | SV bundle sisaldab tehingute nimekirja |
| `test_ml_rows_have_required_fields` | Iga ML rida kannab `account_id`, `record_id`, `value_date`, `signed_amount`, `currency`, `direction` |
| `test_llm_context_has_required_keys` | LLM kontekst sisaldab `meta` (kontometaandmed) ja `tx` (tehingud) |
| `test_report_has_outcome` | Raport sisaldab `outcome.status` välja |
| `test_report_has_summary_counts` | Raport `summary.counts` sisaldab kõiki 6 loendurit |
| `test_report_has_by_severity` | Raport sisaldab CRITICAL/ERROR/WARN/INFO jaotust |
| `test_report_has_issues_list` | Raportil on `issues[]` nimekiri |
| `test_report_has_dropped_details` | Raportil on `dropped_details[]` nimekiri |
| `test_report_run_id_present` | `report.run.run_id` on olemas ja mittetühi |
| `test_report_created_at_utc_present` | `report.run.created_at_utc` on olemas ja mittetühi |
| `test_report_schema_version_present` | Raporti juuretasemel `report_schema_version` on olemas |

### Tulemus

```
13/13 PASSED
```

---

## SLI-02 — Valideerimise läbivus (validation pass-through ratio)

**SLO:** Puhaste ja tootmislaadsete datasettide korral peab SLI-02 olema ≥ 0.99. Kontrollitud vea- ja äärejuhtumite datasettidel raporteeritakse SLI-02 kirjeldava metrikana, mida ei hinnata sama läve alusel.

**Definitsioon:**

SLI-02 mõõdab töötlusse võetud sisendtehingute osakaalu, mis jääb pärast kaardistust, invariantide kontrolli ja deduplikatsiooni standardiseeritud vaheesitusse alles.

SLI-02 = passed_validation_total / input_records_total

kus:
- `input_records_total` = `transactions_total` — kõik sisendtehingud, mis pipeline'i jõuavad
- `passed_validation_total` = `transactions_emitted_sv` — kirjed, mis jäävad pärast kaardistust, invariantide kontrolli ja deduplikatsiooni standardiseeritud vaheesitusse alles
- `dropped_total` = `transactions_dropped` — kõik eemaldatud kirjed
- Identiteet: `input_records_total == passed_validation_total + dropped_total`

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_clean_input_pass_through_ratio_is_one` | Puhas sisend → SLI-02 = 1.0 |
| `test_partial_drops_ratio_between_zero_and_one` | Osalised langetused → 0 < SLI-02 < 1 |
| `test_all_dropped_ratio_is_zero` | Kõik langetatud → SLI-02 = 0.0 |
| `test_ratio_equals_emitted_over_total` | SLI-02 == `transactions_emitted_sv / transactions_total` |
| `test_ratio_consistent_with_dropped_total` | SLI-02 + dropped/total ≈ 1.0 (identity check) |

### Tulemus

```
5/5 PASSED
```

**SLO täidetud: JAH**

---

## QC-02— Eemaldatud kirjete raporteeritavus (operational drop-reporting coverage)

**SLO:** 100 % eemaldatud kirjetest ilmub `report.dropped_details[]` all koos eemaldamise põhjusega.

**Definitsioon:**

QC-02= dropped_details_count / dropped_total (peab olema == 1.0)
QC-02all_drops_reported = (dropped_details_count == dropped_total)

Nulljuhtum (dropped_total == 0): QC-02= 1.0, all_drops_reported = True.

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_valid_input_produces_no_issues` | Puhas sisend → `issues == []` |
| `test_valid_input_outcome_is_success` | Puhas sisend → `status == "SUCCESS"` |
| `test_missing_value_date_produces_issue` | Puuduv `valueDate` → kirje `dropped_details[]` all |
| `test_missing_value_date_drop_reason_contains_valuedate` | Drop reason viitab `valueDate` puudumisele |
| `test_invalid_transaction_is_captured_in_dropped_details` | Vigane tehing → `transactions_dropped > 0` ja `dropped_details` täidetud |
| `test_qc2_all_drops_reported_clean_input` | Puhas sisend → `all_drops_reported == True`, `ratio == 1.0` |
| `test_qc2_all_drops_reported_with_drops` | Langetustega sisend → `all_drops_reported == True` |

### Tulemus

```
7/7 PASSED
```

**SLO täidetud: JAH**

---

## SLI-03 — Invariantide täituvus (invariant compliance ratio)

**SLO:** ≥ 0.999 puhaste/tootmislaadsete datasettide korral; `critical_invariant_violations_total == 0`.

**Definitsioon:**

SLI-03 = invariant_correct_total / invariant_checked_total

kus:
- `invariant_checked_total` (nimetaja) = kirjed, mis jõuavad Stage 4 (CHECK_INVARIANTS) pärast kaardistust, enne deduplikatsiooni. Mapping drops (Stage 2 ebaõnnestumised) **ei kuulu nimetajasse**, sest need kirjed ei jõua kunagi invariantide kontrollini.
- `invariant_correct_total` (lugeja) = invariant_checked_total väheneb järgmiste komponentide võrra:
  - ERROR-taseme invariantrikkumistega langetatud kirjed,
  - deduplikatsioonis (INV-09) eemaldatud kirjed,
  - WARN-lipuga alles jäävad kirjed (nt INV-04, INV-05, INV-10).
- `critical_invariant_violations_total` = kirjed ERROR-taseme invariantrikkumistega (v.a. mapping drops, dedupe, WARN)

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_inv01_bad_currency_drops_transaction` | INV-01: vale valuutaformaat → tehing langetatakse |
| `test_inv02_missing_value_date_drops_transaction` | INV-02: puuduv `valueDate` → tehing langetatakse |
| `test_inv09_duplicate_is_deduplicated` | INV-09: identne tehing → ainult üks säilitatakse SV-s |
| `test_inv09_duplicate_appears_in_dropped_details` | INV-09 duplikaat kajastub `dropped_details[]` all |
| `test_inv04_bad_booking_date_keeps_transaction_as_warn` | INV-04: vigane `bookingDate` → WARN, tehing ei langetata |
| `test_dropped_count_matches_dropped_details` | `counts.transactions_dropped == len(dropped_details)` |
| `test_clean_run_sli3_is_one` | Puhas jooks → SLI-03 = 1.0, critical = 0 |
| `test_error_drops_reduce_compliance_ratio` | ERROR invariant drop → SLI-03 < 1.0 |
| `test_warn_flags_reduce_compliance_ratio` | WARN invariant flag → SLI-03 < 1.0 |
| `test_dedupe_drops_reduce_compliance_ratio` | INV-09 dedupe drops → SLI-03 < 1.0 |
| `test_invariant_correct_total_non_negative` | invariant_correct_total >= 0 alati |
| `test_mapping_drops_excluded_from_sli3_denominator` | Mapping drops ei mõjuta SLI-03 nimetajat |
| `test_dedupe_exact_ratio` | INV-09 dedupe: 3 checked, 1 drop → ratio = 0.6667 |

### Tulemus

```
13/13 PASSED
```

**SLO täidetud: JAH**

---

## Gate — operatiivne kvaliteedivärav (ei ole SLI)

**SLO:** `error_drop_ratio < 5 %` → `PARTIAL_SUCCESS`; `≥ 5 %` → `FAIL`.

**Definitsioon:**

Gate error_drop_ratio = error_drops / input_records_total

Kasutab `count_error_drops()` — sama loogika, mis `determine_outcome()`.

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_gate_error_drop_ratio_in_metrics` | Gate metrikad ilmuvad `metrics.gate` all |
| `test_below_5pct_error_rate_is_partial_success` | 1/21 ≈ 4,8 % < 5 % → `PARTIAL_SUCCESS` |
| `test_at_or_above_5pct_error_rate_is_fail` | 1/10 = 10 % ≥ 5 % → `FAIL` |
| `test_above_5pct_with_bad_currency` | 1/11 ≈ 9 % > 5 % → `FAIL` |
| `test_zero_errors_clean_run_is_success` | Vigadeta jooks → `SUCCESS`, gate = 0 |
| `test_gate_metrics_consistent_with_outcome` | Gate metrikad ja determine_outcome() kasutavad sama loendusloogikat |

### Tulemus

```
6/6 PASSED
```

**SLO täidetud: JAH**

---

## SLI-04 — Determinism

**SLO:** 5 identse sisendi ja sama kellaga jooksu toodavad 100 % identsed väljundi sõnastikud.

**Definitsioon:**

SLI-04 = identsete väljundartefaktidega kordusjooksud / kõik kordusjooksud

SLI-04 ei ole ühe jooksu report.json metrics väli. Hinnatakse 5 kordusjooksu alusel.

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_sv_identical_across_all_runs` | SV bundle on kõigis 5 jooksus identne |
| `test_ml_identical_across_all_runs` | ML read on kõigis 5 jooksus identsed |
| `test_llm_identical_across_all_runs` | LLM kontekst on kõigis 5 jooksus identne |
| `test_report_identical_across_all_runs` | Raport on kõigis 5 jooksus identne |
| `test_run_id_is_fixed` | `run_id` tuleb kellalt, mitte juhuslikust generaatorist |
| `test_created_at_is_fixed` | `created_at_utc` tuleb kellalt, mitte süsteemiajalt |
| `test_all_five_runs_executed` | Kontroll, et tõepoolest käivitati 5 jooksu |

### Report.json stabiilsus

Report.json on determinismi seisukohalt täielikult stabiilne, sest:
- `run_id` ja `created_at_utc` tulevad `FixedClock`-ilt (ei muutu jooksude vahel),
- kõik loendid, metrikad ja issues tekivad deterministlikust domeeniloogikast,
- puuduvad hostispetsiifilised, juhuslikud või kellast sõltuvad väljad.

Seetõttu võrreldakse tervet report.json artefakti, mitte normaliseeritud alamhulka.

### Determinismi tagavad mehhanismid

- **`FixedClock`** — tagastab fikseeritud `run_id` ja UTC ajatempli
- **`_stable_json()`** (`adapters/fs/output_fs.py`) — `sort_keys=True` tagab identse JSON serialisatsiooni
- **`_sort_key()`** (`domain/rules/invariants_r01.py`) — deterministlik tiebreaker duplikaatide eemaldamiseks
- **Fikseeritud CSV veeruorder** — `_ML_FIELDNAMES` konstantne järjekord

### Tulemus

```
7/7 PASSED
```

**SLO täidetud: JAH**

---

## SLI-05 — Auditijälje täielikkus

**SLO:** 100 % jooksudest sisaldab kõiki nõutud auditivälju `report.run` sektsioonis.

**Definitsioon:**

SLI-05 = sisuliselt olemasolevad nõutud auditiväljad / kõik nõutud auditiväljad

Kohustuslikud auditiväljad: `sv_schema_version`, `mapping_version`, `ruleset_version`, `adapter_version`.

Sisuline olemasolu tähendab:
- väli on report.run sektsioonis olemas,
- väärtus ei ole None,
- väärtus ei ole tühi ega ainult tühikutest koosnev string.

Soovitavad lisaväljad (kui teostus võimaldab): `spec_lock_sha256`, `input_fingerprint`, `output_artifact_hashes`.

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_sli5_all_required_audit_fields_present` | Kõik 4 kohustuslikku auditivälja on sisuliselt olemas |
| `test_sli5_completeness_ratio_is_one` | SLI-05 `sli5_audit_completeness_ratio == 1.0` |
| `test_sli5_detects_missing_field` | Puuduv auditiväli vähendab SLI-05 suhtarvu |
| `test_sli5_none_value_is_not_substantive` | None väärtus ei ole sisuline olemasolu |
| `test_sli5_empty_string_is_not_substantive` | Tühi string ei ole sisuline olemasolu |
| `test_sli5_whitespace_only_is_not_substantive` | Ainult tühikutest koosnev string ei ole sisuline |
| `test_sli5_sv_schema_version` | `report.run.sv_schema_version` on olemas ja mittetühi |
| `test_sli5_mapping_version` | `report.run.mapping_version` on olemas ja mittetühi |
| `test_sli5_ruleset_version` | `report.run.ruleset_version` on olemas ja mittetühi |
| `test_sli5_adapter_version` | `report.run.adapter_version` on olemas ja mittetühi |

### Tulemus

```
10/10 PASSED
```

**SLO täidetud: JAH**

---

## SLI-06 — Referentsjõudlus

**Definitsioon:**

SLI-06 = mediaanne töötlusaeg referentsandmestikul

Mõõtmismetoodika:
1. 1 proovijooks, mille tulemust lõppnäitajasse ei arvestata
2. 3 mõõdetud jooksu
3. Tulemuseks on nende 3 mõõdetud jooksu mediaan

SLI-06 ei kuulu report.json metrics sektsiooni. See on eraldi mõõtmise tulemus.

### Mida testitakse

| Test | Kontrollib |
|------|-----------|
| `test_sli6_reference_benchmark` | Mõõdab referentsjõudlust 1000 tehinguga andmestikul |
| `test_sli6_median_is_positive` | Mediaan on positiivne arv |
| `test_sli6_three_measured_runs` | Mõõtmistulemus sisaldab täpselt 3 mõõdetud aega |

### Tulemus

```
3/3 PASSED
```

---

## Kokkuvõte

| SLI | SLO sihtmärk | Mõõtetase | Testide arv | Tulemus | SLO täidetud |
|-----|-------------|-----------|------------|---------|-------------|
| SLI-01 Skeemikatvus | ≥ 0.95 | Spetsifikatsioon | 8 | 8/8 ✓ | **JAH** |
| Struktuurne terviklikkus | (kontroll) | — | 13 | 13/13 ✓ | — |
| SLI-02 Valideerimise läbivus | ≥ 0.99 (puhas) | Jooksupõhine | 5 | 5/5 ✓ | **JAH** |
| QC-02Eemaldatud kirjete raporteeritavus | 100 % | Jooksupõhine | 7 | 7/7 ✓ | **JAH** |
| SLI-03 Invariantide täituvus | ≥ 0.999; critical == 0 | Jooksupõhine | 13 | 13/13 ✓ | **JAH** |
| Gate Operatiivne kvaliteedivärav | < 5 % / ≥ 5 % | Jooksupõhine | 6 | 6/6 ✓ | **JAH** |
| SLI-04 Determinism (N=5) | 100 % | Mitme jooksu võrdlus | 7 | 7/7 ✓ | **JAH** |
| SLI-05 Auditijälje täielikkus | 100 % | Jooksupõhine | 10 | 10/10 ✓ | **JAH** |
| SLI-06 Referentsjõudlus | Informatiivne referentsmõõtmine | Eraldi mõõtmine | 3 | 3/3 ✓ | **mõõdetud** |
| **KOKKU** | | | **72** | **72/72** | |
