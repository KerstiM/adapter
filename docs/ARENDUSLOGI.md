# Arenduslogi

Prototüübi arenduse kronoloogiline ülevaade.

---

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
