# Spetsifikatsioonid

Adapteri käitumine on määratud versioonitud spetsifikatsioonifailidega. Pärast failide lukustamist ei tohiks prototüübi semantikat enam muuta, vaid ainult täiendada uute versioonidega.

---

## Skeemid (`spec/schemas/`) — andmete kuju

| ID | Fail | Kirjeldus |
|----|------|-----------|
| S-00A | `S-00A_berlin_accounts.schema.json` | Sisendi `accounts.json` struktuur (min `resourceId`, `iban`, `currency`). Tagab, et testandmestikud on valideeritavad. |
| S-00B | `S-00B_berlin_transactions.schema.json` | Sisendi `transactions.json` struktuur. `ReportResponse.account.iban` on kohustuslik, et C-01 saaks tehingud kontoga siduda. |
| S-01 | `S-01_sv_schema.json` | Standardiseeritud vaheesituse (SVBundle) skeem: meta + accounts + transactions. Prototüübi keskne kanooniline kuju. |
| S-02 | `S-02_ml_projection_schema.json` | ML CSV rea miinimumveerud ja tüübid. Võimaldab väljundi automaatset valideerimist. |
| S-03 | `S-03_llm_context_schema.json` | LLM kontekstobjekti struktuur (JSON). Tagab, et LLM sisend on stabiilne ja masinloetav. |
| S-05 | `S-05_collected_report_schema.json` | Jooksu koondraport (status, issues, dropped_details, loendused). Toetab auditeeritavust. |

## Lepingud (`spec/contracts/`) — teisendused

| ID | Fail | Kirjeldus |
|----|------|-----------|
| C-01 | `C-01_berlin_to_sv.yaml` | Berlin/PSD2 sisend → SV: kaardistus, normaliseerimine, ID tuletus, veakäsitlus. |
| C-02 | `C-02_sv_to_ml.yaml` | SV → ML CSV: veerud, filtrid, sortimine, tuletised. |
| C-03 | `C-03_sv_to_llm.yaml` | SV → LLM kontekst: aknastamine (nt last-N), truncation, sortimine. |

## Reeglistikud (`spec/rulesets/`) — invariandid

| ID | Fail | Kirjeldus |
|----|------|-----------|
| R-01 | `R-01_sv_invariants.yaml` | SV invariandid (ERROR/WARN + tegevus). Määrab, millal kirje dropitakse, millal flagitakse ja kuidas kujuneb jooksu staatus. |

## Profiilid (`spec/profiles/`) — komplekt jooksuks

| Fail | Kirjeldus |
|------|-----------|
| `default.yaml` | Seob kokku skeemid, lepingud ja reeglistiku ning määrab `partial_success_policy` (sh FAIL tingimused, nt ERROR ratio > 5%). |
