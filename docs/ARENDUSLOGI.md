# Arenduslogi

Prototüübi arenduse kronoloogiline ülevaade.
DSR iteratsioonid on märgistatud tsükliga: **ehita → hinda → õpi → kohanda**.

---

## Iteratsioon 1: Esialgne pipeline ja testimine (10.–12.02)

### 2026-02-10
- Spetsifikatsioonide algversioon: R-01 invariandid

### 2026-02-11
- **Happy-path pipeline** valmis: RAW (Berlin AIS) → SV → ML/LLM projektsioonid → raport
- Pipeline ümberkirjutus vastavusse spec v2-ga (S-01, C-01/C-02/C-03)
- Refaktor: ühtne RunContext, jooksukaustad, report.json
- Vana koodi puhastus (core.py, io_excel.py, io_json.py)
- Tehingute drop-loenduse parandus ja valueDate fallback-poliitika

### 2026-02-12
- Dataseti generaator ja D1–D6 testdatasetid
- CLI `--data/-d` lipp dataseti valimiseks

**Hindamine:** Pipeline käivitatud D1–D3 andmestikel — happy-path töötab.
**Õpitu:** Pipeline töötab validsetel andmetel, kuid vigade käsitlemine (vale valuuta, puuduv kuupäev) ja deduplitseerimine puuduvad. Fail-gate mehhanism vajalik.
**Kohandus:** → viib iteratsiooni 2.

---

## Iteratsioon 2: Vigade käsitlemine ja valideerimine (13.–16.02)

### 2026-02-13
- D4: deterministlik FAIL-dataset (>5% drop threshold)
- INV-09 duplikaadireegli lisamine R-01-sse (v1.1.0)
- Dedupe samm ja fail-gate pipeline'is
- D6: duplikaatide testdataset

### 2026-02-16
- **Skeemide/lepingute valideerimine ja lepitamine:**
  - S-05 raporti skeem: täielik ümberkirjutus (outcome enum, struktureeritud issues, by_stage massiiv)
  - S-03 LLM kontekst: lisatud `oneOf` (objekt / massiiv mitme konto korral)
  - default.yaml: parandatud S-00A/S-00B failiteed
  - C-03: uuendatud mitme konto kardinaalsus
- S-00C püsikorralduste skeem + profiili sidumine
- D7 püsikorralduste dataset + valueDate fallback parandus
- Valideerimistulemus: 35/36 PASS (1 oodatud FAIL D4-l)

**Hindamine:** 35/36 PASS, D4 annab oodatud FAIL (10,3% veamäär > 5% lävend). D6 dedupleerimine tabab 3 duplikaati.
**Õpitu:** S-05 raporti skeem vajas täielikku ümberkirjutust — esialgne struktuur ei kajastanud `by_stage` ega `dropped_details[]` massiive. S-03 vajas `oneOf` toetust mitme konto korral. R-01 versioon tõstetud v1.1.0-ks (INV-09 lisamine).
**Kohandus:** Skeemid ümber kirjutatud, reeglistik uuendatud.

---

## Iteratsioon 3: Ports & Adapters arhitektuurirefaktor (17.–22.02)

### 2026-02-17
- **Golden/regressioonitestid:** freeze_goldens.py, verify_goldens.py, spec.lock.json
- **QA entrypoint:** run_full_qa.py (5-etapiline E2E kontroll)
- D3 mitme konto versioon (eraldi tehingufailid)
- frozen/v1.0.0/ struktuur (manifest + goldenid)

### 2026-02-18
- **Ports & Adapters refaktor algus:**
  - Sihtstruktuuri kaustad
  - Portide liidesed (SpecPort, DatasetPort, OutputPort, ClockPort)
  - FS-adapterid kõigile portidele
  - Pipeline orkestreerimine portide kaudu (mitte otse failisüsteemist)
- Puhas loogika eraldatud `domain/` moodulisse
- frozen/v1.0.0 lukustamine

### 2026-02-19
- Arhitektuuri importimispiiride test (`test_import_boundaries.py`)
- Veakataloog → reeglistikud; plaanid → docs/

### 2026-02-21
- **Compat-kihi eemaldamine:**
  - `entrypoints/wiring_fs.py` kui FS driving-adapter
  - `run_adapter.py` ümber ühendatud läbi wiring_fs
  - Fake-portide unit-testid `run_pipeline`-le
  - Testide sõltuvus compat-kihist eemaldatud
  - `backend/adapter/` (vana compat-kiht) kustutatud
- README uuendatud peegeldama Ports & Adapters arhitektuuri

### 2026-02-22
- Dokumentatsiooni ümberkorraldus: minimaalne eestikeelne komplekt
- Duplikaatfailide kustutamine (NOTES.md, VALIDATION_REPORT.md)
- 4 uut tuumdokumenti: ARHITEKTUUR, ARENDUSLOGI, TESTIMINE, SPETSIFIKATSIOONID

**Hindamine:** Import boundary test kinnitab: domeeniloogika ei impordi adaptereid ega infrastruktuuri. Golden-regressioonitestid läbivad kõik 7 andmestikku. QA entrypoint 5-etapiline kontroll PASS.
**Õpitu:** Compat-kiht (vana `backend/adapter/`) on ebavajalik — `wiring_fs.py` ühendab FS-adapterid otse portidega. Fake-portidega testimine on oluliselt lihtsam ja kiirem kui failisüsteemi kaudu.
**Kohandus:** Compat-kiht kustutatud. Puhas Ports & Adapters arhitektuur saavutatud.

---

## Iteratsioon 4: Koormustestimine (28.02)
- **D8 koormustesti andmestik:** 10 000 tehingut (8 000 booked + 2 000 pending), seed 88
- **Eesmärk:** Tõendada pipeline'i käitumist tootmismahtudel — determinism, jõudlus, mäluhaldus
- **Tulemused:**
  - Jõudlus: mediaan 3 381,40 ms (stddev 77,07 ms, läbilaskevõime 2,957 tx/ms) SLI-6 metoodikaga (1 proovijooks + 5 mõõdetud jooksu)
  - Determinism: 100% — kõik 4 artefakti (sv.json, report.json, ml_v1.csv, llm_context_v1.json) baidilt identsed kahe jooksu vahel
  - Tulemus: SUCCESS (0 droppi, 0 hoiatust)
  - LLM aknastamine N=200 töötas korrektselt ka 10 000 tehinguga
- **Järeldused:**
  - SLI-6 viitejõudluse SLO (D9, 1000 tx, mediaan ≤ 500 ms) mõõdetakse `FakeOutputPort`-iga (in-memory, ilma FS I/O-ta); 10 000 tehinguga reaalse FS-iga on 3 381,40 ms — see on eraldi mõõtmismeetod, mitte SLO rikkumine
  - SHA-256 record_id (16 hex-märki / 64 bitti) kokkupõrkeid ei tekkinud 10 000 kirje juures
  - Pipeline skaleerub lineaarselt — pudelikaelaks on JSON serialiseerimine ja sortimine
- **Uuendused:** D8 golden-väljundid lisatud, frozen/v1.0.0/manifest.json uuendatud (8 andmestikku)

---

## Iteratsioon 5: MF6 valideerimine ja skaleeruvusanalüüs (02.03)
- **D9 standardmahu andmestik:** 1 000 tehingut (800 booked + 200 pending), seed 9
- **Eesmärk:** Valideerida MF6 nõue (≤ 500 ms standardse testandmestiku jaoks, ~kuue kuu kontoväljavõte) ning täiendada skaleeruvusanalüüsi vahepunktiga (D1: 7 tx → D9: 1 000 tx → D8: 10 000 tx)
- **Tulemused:**
  - Jõudlus: mediaan 373,71 ms (stddev 4,41 ms, läbilaskevõime 2,676 tx/ms) — MF6 SLO (≤ 500 ms) täidetud
  - Tulemus: SUCCESS (0 droppi, 0 hoiatust)
  - Kolme punkti skaleeruvustabel: D1 (7 tx, ~55 ms), D9 (1 000 tx, 373,71 ms), D8 (10 000 tx, 3 381,40 ms)
- **Järeldused:**
  - MF6 SLO (≤ 500 ms) kehtib kinnitatult kuni 1 000 tehinguni
  - Kolme andmepunkti põhjal on tulemus kooskõlas O(n) keerukusega püsikuludega (~50 ms startup); D8/D9 läbilaskevõime (2,957 vs 2,676 tx/ms) on samas suurusjärgus, mis kinnitab ligikaudu lineaarset skaleerumist ja fikseeritud püsikulude amortiseerumist suurema mahu juures
  - TestDeterminism uuendatud N=5 jooksule (varasem N=2 oli ebapiisav)
- **Uuendused:** D9 golden-väljundid lisatud, frozen/v1.0.0/manifest.json uuendatud (9 andmestikku)

---

## Iteratsioon 6: Reaalne de-identifitseeritud andmestik (04.03)
- **D10 reaalne de-identifitseeritud andmestik:** 90 tehingut (okt–nov 2016), parsitud pangaväljavõttest
- **Eesmärk:** Valideerida pipeline'i käitumist pärisandmetega; tõendada, et süsteem töötab ka väljaspool sünteetilisi datasette (UK2 auditeeritav kvaliteeditõendus)
- **Töötlusaste:** osaliselt pseudonümiseeritud ja perturbeeritud (vt täiendav selgitus iteratsioonis 7)
- **Kasutatud tehnikad (täiendatud 16.04):**
  - Pseudonümiseerimine: isikute nimed asendatud väljamõeldud nimedega (4 isikut)
  - Pseudonümiseerimine: isiklikud IBANid asendatud (11 unikaalset kontot)
  - Pseudonümiseerimine: kaardi viimased 4 numbrit muudetud (2 kaarti)
  - Üldistamine: POS-aadressid (töökoha ja elukoha tuvastamine välistatud)
  - Üldistamine: remittance-tekstid puhastatud identifitseerivatest viidetest (perekondlikud viited eemaldatud)
  - Perturbatsioon: summad ±5–15%, palgasumma normaliseeritud
  - Säilitatud: ettevõtete nimed ja avalikud IBANid (avalik info)
- **Huvitavad äärjuhud:**
  - Duplikaat-transactionId 47210131 (ATM väljavõte + teenustasu — erinev sisu, sama ID)
  - `creditorName: "nan"` (pandas NaN→string artefakt)
  - Teaduslik notatsioon `remittanceInformationStructured`-is (Excel/pandas artefakt)
- **Tulemused:**
  - Pipeline tulemus: PARTIAL_SUCCESS (oodatud — pärisandmetes tekivad WARN-lipud)
  - 101 väljundrida (90 booked + 11 tuletatud)
  - Determinism: 100% — kõik 4 artefakti baidilt identsed
  - Kõik skeemid valideeruvad
- **Uuendused:** D10 golden-väljundid lisatud, frozen/v1.0.0/manifest.json uuendatud (10 andmestikku)

---

## Iteratsioon 7: Terminoloogia täpsustus ja andmestike ümbernimetamine (17.04)

- **Põhjus:** Senised nimetused `D10_real_anon_oct16` ja `D11_real_anon_2024`
  viitasid "anonümiseerimisele", kuid kasutatud tehnikad (identifikaatorite
  asendamine + kvaasi-identifikaatorite säilitamine + summade perturbatsioon)
  ei vasta ei GDPR art 4(5) pseudonümiseerimise täisnõuetele ega
  anonümiseerimise nõuetele. Auditeeritav kvaliteeditõendus (UK2) nõuab, et
  kaustanimi ja dokumentatsioon peegeldaksid tegelikku töötlusastet.
- **Täpsem termin:** **osaliselt pseudonümiseeritud ja perturbeeritud**
  (ingl *de-identified test dataset*). Puudub eraldi turvaliselt hoitud
  võtmehoidla, mistõttu ei ole tegemist täieliku pseudonümiseerimisega
  GDPR mõttes. Säilivad kvaasi-identifikaatorid (kuupäevad, tehingumustrid,
  avalikud IBAN-id, firmanimed) võimaldavad korrelatsiooniga
  re-identifitseerimist — seega pole tegemist ka anonümiseerimisega.
- **Muudatused:**
  - Kaustad ümber nimetatud:
    `datasets/D10_real_anon_oct16` → `datasets/D10_real_deid_oct16`
    `datasets/D11_real_anon_2024` → `datasets/D11_real_deid_2024`
    (sama `golden/`-is)
  - Koodi-viited uuendatud: `.pre-commit-config.yaml`, `.gitignore`,
    `scripts/freeze_goldens.py`, `scripts/reanonymise_pii.py`,
    `frontend/src/services/api.js`,
    `frontend/src/data/docs.js`,
    `backend/tests/test_integration_fs.py`
  - D10 ja D11 README-desse lisatud sektsioon **"Töötlusaste ja GDPR-staatus"**
    viitega GDPR art 4(5)-le
  - Live goldenid `golden/D10_real_deid_oct16/` ja
    `golden/D11_real_deid_2024/` regenereeritud pipeline'i kaudu (uued
    `dataset_id`, `input_dir`, `run_id` väljad)
  - Uus `frozen/v1.1.0/` snapshot loodud uute nimedega ja värskelt arvutatud
    SHA-256 hash'idega; `frozen/v1.0.0/` jääb ajaloolise auditeeritava
    snapshot'ina **puutumata**
- **Tulemused:**
  - `grep -r "real_anon"` (v.a `frozen/v1.0.0/`) tagastab tühja
  - Kõik integratsioonitestid läbivad uute andmestikunimedega
  - Terminoloogia GDPR-vastavalt täpsem, auditi-jälgitavus säilitatud
