# Spetsifikatsioonifailide ülevaade

Adapteri käitumine on täielikult määratud versioonitud spetsifikatsioonifailidega (`spec/` kataloogis). Allpool on iga faili lühikirjeldus.

---

## Skeemid (schemas/) — *mis kujuga andmed peavad olema*

| Fail | Mis see on | Milleks kasutatakse |
|------|-----------|---------------------|
| **S-01** `sv_schema.json` | SV (standardiseeritud vaheesituse) JSON Schema | Valideerib, et adapteri väljund (SVBundle) vastab struktuurile: jooksu metaandmed, kontod, tehingud. Kõik tüübid, kohustuslikud väljad ja formaadid (nt UTC ajatempel, ISO 4217 valuuta) on siin fikseeritud. |
| **S-02** `ml_projection_schema.json` | ML-projektsiooni rea skeem | Valideerib, et iga ML-sisendtabeli rida sisaldab nõutud veerge (`row_id`, `amount`, `direction` jne). Väljund on CSV. |
| **S-03** `llm_context_schema.json` | LLM kontekstobjekti skeem | Valideerib LLM-ile ette antava JSON-objekti struktuuri: meta, konto kontekst, tehingute loend. |
| **S-04** `llm_output_schema.json` | LLM väljundi skeem | Valideerib LLM-i tagastatavat masinloetavat tulemust (nt kategooria, kindlus, põhjendus). Võimaldab automaatset hindamist. |
| **S-05** `collected_report_schema.json` | Koondraport | Valideerib jooksu lõpus tekkivat raportit: staatus, loendused, probleemikirjed, mõõdikud. Auditeeritavuse alus. |

---

## Lepingud (contracts/) — *kuidas andmeid teisendatakse*

| Fail | Sisend → Väljund | Mida kirjeldab |
|------|-------------------|----------------|
| **C-01** `ob_to_sv.yaml` | Open Banking JSON → SV | Väljade kaardistus (nt `$.transactionAmount.amount` → `amount`), normaliseerimisreeglid (tekst lowercase, ajad UTC, valuuta uppercase), ID-arvutuse loogika ja vigade käitlemise poliitika (`DROP_RECORD`, `WARN` jne). |
| **C-02** `sv_to_ml.yaml` | SV → ML tabel (CSV) | Millised SV väljad lähevad ML-tabelisse, millised tuletised lisatakse (`amount_abs`, `month`, `weekday`), sortimisvõti ja filtrid (`BOOKED` only). |
| **C-03** `sv_to_llm.yaml` | SV → LLM kontekst (JSON) | Tehingute aknastamine (`LAST_N: 200`), kirjelduse kärpimine (160 märki), väljanimede lühendamine (`booking_time_utc` → `t`) ja sorteerimine. |

---

## Reeglistik (rulesets/) — *mida kontrollitakse*

| Fail | Mida kirjeldab |
|------|----------------|
| **R-01** `sv_invariants.yaml` | 10 invarianti, mida iga SV tehing peab täitma. Iga reegli juures on tõsidus (`CRITICAL`/`WARN`) ja toime (`DROP_RECORD`, `FLAG_ONLY`, `NORMALIZE_AND_FLAG`). Nt: `booking_time_utc` peab olema parsitav UTC; `currency` peab vastama ISO 4217; duplikaadid eemaldatakse deterministlikult. |
| `error_catalog.yaml` | Veakoodide kataloog (praegu tühi kohatäide). |

---

## Profiil (profiles/) — *mis komplekt kokku läheb*

| Fail | Mida kirjeldab |
|------|----------------|
| **default.yaml** | Seob kõik eelnevad failid üheks konfiguratsiooniks: millist skeemi, reeglistikku ja lepinguid üks jooks kasutab. Sisaldab ka globaalseid poliitikaid (`drop_on_required_null`, `status_allowlist`). |

---

## Kokkuvõte

```
spec/
├── schemas/          ← Andmete kuju (JSON Schema valideerib)
│   ├── S-01  SV skeem
│   ├── S-02  ML projektsiooni skeem
│   ├── S-03  LLM konteksti skeem
│   ├── S-04  LLM väljundi skeem
│   └── S-05  Raporti skeem
├── contracts/        ← Teisendusreeglid (kuidas X → Y)
│   ├── C-01  Open Banking → SV
│   ├── C-02  SV → ML
│   └── C-03  SV → LLM
├── rulesets/         ← Valideerimisreeglid (mida kontrollitakse)
│   ├── R-01  SV invariandid
│   └── error_catalog (kohatäide)
└── profiles/         ← Konfiguratsioon (mis komplekt kokku läheb)
    └── default.yaml
```

Kõik failid on versioonitud (`*_version: "1.0.0"`) ja viitavad üksteisele ID kaudu. Adapteri kood loeb profiili, laeb sealt viidatud failid ja täidab neis kirjeldatud reegleid. Kui reegleid muudetakse, muutub versiooninumber ja SVBundle metaandmed kajastavad, milliste versioonidega jooks tehti.
