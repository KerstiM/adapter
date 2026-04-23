# Spetsifikatsioonid

Adapteri käitumine on määratud versioonitud spetsifikatsioonifailidega. Pärast failide lukustamist ei tohiks prototüübi semantikat enam muuta, vaid ainult täiendada uute versioonidega.

---

## Skeemid (`spec/schemas/`) — andmete kuju

| ID | Fail | Kirjeldus |
|----|------|-----------|
| S-00A | `S-00A_berlin_accounts.schema.json` | Sisendi `accounts.json` struktuur (min `resourceId`, `iban`, `currency`). Tagab, et testandmestikud on valideeritavad. |
| S-00B | `S-00B_berlin_transactions.schema.json` | Sisendi `transactions.json` struktuur. `ReportResponse.account.iban` on kohustuslik, et C-01 saaks tehingud kontoga siduda. |
| S-00C | `S-00C_berlin_standing_orders.schema.json` | Sisendi `standing_orders.json` struktuur. Valikuline sisend — kui dataset sisaldab püsikorraldusi, valideeritakse neid selle skeemi vastu. |
| S-01 | `S-01_sv_schema.json` | Standardiseeritud vaheesituse (SVBundle) skeem: meta + accounts + transactions. Prototüübi keskne kanooniline kuju. |
| S-02 | `S-02_ml_projection_schema.json` | ML CSV rea miinimumveerud ja tüübid. Võimaldab väljundi automaatset valideerimist. |
| S-03 | `S-03_llm_context_schema.json` | LLM kontekstobjekti struktuur (JSON). Tagab, et LLM sisend on stabiilne ja masinloetav. |
| S-05 | `S-05_collected_report_schema.json` | Jooksu koondraport (status, issues, dropped_details, loendused). Toetab auditeeritavust. |
| S-06 | `S-06_stats_schema.json` | Statistika projektsiooni skeem: kontode ja tehingute kokkuvõtted (summa, arv kontode kaupa). Kasutatakse `extensions_eval` profiiliga. |
| S-07 | `S-07_monthly_balance_schema.json` | Kuubilansi projektsiooni skeem: igakuised saldod kontode kaupa. Kasutatakse `extensions_eval` profiiliga. |

## Lepingud (`spec/contracts/`) — teisendused

| ID | Fail | Kirjeldus |
|----|------|-----------|
| C-01 | `C-01_berlin_to_sv.yaml` | Berlin/PSD2 sisend → SV: kaardistus, normaliseerimine, ID tuletus, veakäsitlus. |
| C-02 | `C-02_sv_to_ml.yaml` | SV → ML CSV: veerud, filtrid, sortimine, tuletised. |
| C-03 | `C-03_sv_to_llm.yaml` | SV → LLM kontekst: aknastamine (nt last-N), truncation, sortimine. |
| C-04 | `C-04_model_formatters.yaml` | Mudelispetsiifilised formaatijad. LLM: promptimallid (Llama 3, Mistral, ChatML/Qwen). ML: kodeeringud (XGBoost label-encoding, CatBoost native). Pipeline etapp 7 (`FORMAT_FOR_MODEL`) kasutab seda lepingut. |
| C-05 | `C-05_sv_to_stats.yaml` | SV → statistika: kontode ja tehingute kokkuvõtted. Aktiveeritakse `projections` loetelu kaudu (nt `extensions_eval` profiil). |
| C-06 | `C-06_sv_to_monthly_balance.yaml` | SV → kuubilanss: igakuised saldod kontode kaupa. Aktiveeritakse `projections` loetelu kaudu (nt `extensions_eval` profiil). |

## Reeglistikud (`spec/rulesets/`) — invariandid

| ID | Fail | Kirjeldus |
|----|------|-----------|
| R-01 | `R-01_sv_invariants.yaml` | SV invariandid (ERROR/WARN + tegevus). Määrab, millal kirje dropitakse, millal flagitakse ja kuidas kujuneb jooksu staatus. INV-01..INV-05, INV-09. |
| — | `error_catalog.yaml` | Veakoodide kataloog: loetleb kõik pipeline'i emiteeritavad `issues[].code` väärtused koos vaikimisi tõsiduse, etapi ja kirjeldusega. Toetab raporti auditeeritavust. |

## Profiilid (`spec/profiles/`) — komplekt jooksuks

| Fail | Kirjeldus |
|------|-----------|
| `default.yaml` | Baasprofiil: seob skeemid (S-00A..S-05), lepingud (C-01..C-04) ja reeglistiku (R-01). Määrab `projections: [ml, llm]` ja `partial_success_policy` (FAIL tingimused: ERROR ratio > 5%). |
| `extensions_eval.yaml` | Laiendatud profiil: lisab skeemid S-06/S-07, lepingud C-05/C-06 ja `projections: [ml, llm, stats, monthly_balance]`. Kasutatakse laiendatud projektsioonide hindamiseks (`--profile extensions_eval`). |
