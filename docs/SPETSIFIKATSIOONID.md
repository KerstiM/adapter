# Spetsifikatsioonid

Adapteri käitumine on määratud versioonitud spetsifikatsioonifailidega `spec/` kataloogis. Pärast lukustamist (`frozen/v*/`) muudetakse semantikat ainult uue versiooni kaudu.

## Skeemid (`spec/schemas/`)

| ID | Fail | Kasutus |
|----|------|---------|
| S-00A | `S-00A_berlin_accounts.schema.json` | RAW `accounts.json` (min `resourceId`, `iban`, `currency`) |
| S-00B | `S-00B_berlin_transactions.schema.json` | RAW `transactions.json`; `account.iban` kohustuslik, et C-01 saaks tehingu kontoga siduda |
| S-00C | `S-00C_berlin_standing_orders.schema.json` | RAW `standing_orders.json` (valikuline) |
| S-01 | `S-01_sv_schema.json` | SVBundle — prototüübi keskne kanooniline kuju |
| S-02 | `S-02_ml_projection_schema.json` | ML CSV rea miinimumveerud ja tüübid |
| S-03 | `S-03_llm_context_schema.json` | LLM konteksti kuju (stabiilne, masinloetav) |
| S-05 | `S-05_collected_report_schema.json` | Koondraport (status, issues, dropped_details, loendused) |
| S-06 | `S-06_stats_schema.json` | Statistika projektsioon (extensions_eval) |
| S-07 | `S-07_monthly_balance_schema.json` | Kuubilansi projektsioon (extensions_eval) |

## Lepingud (`spec/contracts/`)

| ID | Fail | Teisendus |
|----|------|-----------|
| C-01 | `C-01_berlin_to_sv.yaml` | Berlin/PSD2 → SV (kaardistus, normaliseerimine, ID tuletus, veakäsitlus) |
| C-02 | `C-02_sv_to_ml.yaml` | SV → ML CSV (veerud, filtrid, sortimine, tuletised) |
| C-03 | `C-03_sv_to_llm.yaml` | SV → LLM kontekst (aknastamine, truncation, sortimine) |
| C-04 | `C-04_model_formatters.yaml` | Pipeline etapp 7 `FORMAT_FOR_MODEL`: LLM promptimallid + ML kodeeringud |
| C-05 | `C-05_sv_to_stats.yaml` | SV → statistika (kontode ja tehingute kokkuvõtted) |
| C-06 | `C-06_sv_to_monthly_balance.yaml` | SV → kuubilanss (igakuised saldod kontode kaupa) |

## Reeglistikud (`spec/rulesets/`)

| ID | Fail | Sisu |
|----|------|------|
| R-01 | `R-01_sv_invariants.yaml` | INV-01..INV-05, INV-09 (drop/flag + tõsidus) |
| — | `error_catalog.yaml` | Pipeline'i `issues[].code` väärtused |
| — | `QC_quality_checks.yaml` | QC-1 INFO-tasemel kontroll |

## Profiilid (`spec/profiles/`)

| Fail | `projections` | Kasutus |
|------|---------------|---------|
| `default.yaml` | `[ml, llm]` | Baasprofiil; gate `ratio_over_records=0.05` |
| `extensions_eval.yaml` | `[ml, llm, stats, monthly_balance]` | Laiendatud projektsioonide hindamine |
