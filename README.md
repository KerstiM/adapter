# Arenduslogi

## 2025-11-21

### Muudatused
- [x] Loon projekti struktuuri `backend/` ja `frontend/` kaustadega.
- [x] Loon Pythoni virtuaalkeskkonna `backend/venv` alla.

### Põhjendus
- **Eraldi `backend` ja `frontend` kaustad**  
  - `backend`: Pythoni adapter, mis tegeleb andmete lugemise, transformatsiooni ja mudeli sisendite genereerimisega.  
  - `frontend`: Vue/JavaScript kiht, millega saab hiljem tulemusi visualiseerida või prototüübi kasutusvoogu demonstreerida.  
  - Selline eraldatus hoiab andmetöötluse loogika ja kasutajaliidese eraldi ning teeb projekti ülesehituse arusaadavamaks.

- **Virtuaalkeskkond (`venv`) backendis**  
  - Hoian projekti jaoks eraldi virtuaalkeskkonda konkreetse Pythoni versiooni ja muude sõltuvustega, et:
    - mitte panna kõiki projekte sõltuma ühest globaalsest Pythonist ja paketikomplektist; 
    - vältida konflikte eri projektide paketiversioonide vahel; 
    - muuta projekti keskkond taasesitatavaks: sama Pythoni versioon ja samad sõltuvused on taastatavad `venv + requirements.txt` abil. 
      - `python -m venv venv` + `pip install -r requirements.txt` taastab sama keskkonna.
    > **Märkus:** `backend/venv` kataloogi sisu on automaatselt genereeritud virtuaalkeskkond (Pythoni tõlgid ja paketid) ning seda tavaliselt versioonihalduses ei hoita; keskkond on taasesitatav käsuga `python -m venv venv` ja `pip install -r requirements.txt`.
    ::contentReference[oaicite:0]{index=0}

## 2025-11-21 – projekti esmane seadistus

```bash
# Loon Pythoni virtuaalkeskkonna (eraldi keskkond ainult selle projekti jaoks)
cd /path/to/project/backend
python3 -m venv venv

# Aktiveerin virtuaalkeskkonna (edasi kasutatav python/pip viitab venv'ile)
source venv/bin/activate

# Installin pandas teegi Exceli/andmete töötlemiseks
pip install pandas

# Installin openpyxl teegi, mida pandas kasutab .xlsx failide lugemiseks
pip install openpyxl

# Salvestan projekti Pythoni sõltuvused requirements.txt faili
pip freeze > requirements.txt
```

## 2026-02-11 – Happy-path pipeline ja skeemid

### Mida tegin
- [x] Lisasin Berlin AIS (PSD2) sisendandmete skeemid: `S-00A_berlin_accounts.schema.json`, `S-00B_berlin_transactions.schema.json`
- [x] Lisasin väljundskeemid: `S-01_sv_schema.json` (SVBundle), `S-02_ml_projection_schema.json`, `S-03_llm_context_schema.json`
- [x] Lisasin lepingud (contracts): `C-01_berlin_to_sv.yaml`, `C-02_sv_to_ml.yaml`, `C-03_sv_to_llm.yaml`
- [x] Lisasin reeglid: `R-01_sv_invariants.yaml` (6 invarianti)
- [x] Lisasin D1 testiandmestiku: `accounts.json`, `transactions.json`, `standing_orders.json`, `transactions_download.json`
- [x] Realiseerisin `backend/adapter/pipeline.py` — täielik pipeline RAW (Berlin AIS JSON) → SV (kanooniline) → ML projektsioon (CSV) + LLM projektsioon (JSON) + raport
- [x] Kirjutasin 26 happy-path testi (`backend/tests/tests.py`): SV skeemivalidatsioon, suuna tuletamine, summade normaliseerimine, ML/LLM projektsioonide kontroll, determinismi test
- [x] Kõik 26 testi läbivad edukalt

### Miks
- **Pipeline** realiseerib lõputöö prototüübi tuumiku: sisend (Berlin AIS) → standardiseeritud vaheesitus (SV) → mudelispetsiifilised projektsioonid (ML ja LLM)
- **Skeemid** ja **lepingud** tagavad, et pipeline käitumine on deklaratiivselt määratud ja valideeritav
- **Testid** tõendavad, et D1 andmestiku happy-path töötab korrektselt ja on determineeritud (sama sisend → sama väljund)

### Tehniline ülevaade
- **Suuna tuletamine (C-01):** `debtorName` → IN, `creditorName` → OUT, varuvariant summa märgi põhjal
- **Summa objekt (S-01):** `{currency, raw, signed, abs}` — OUT = negatiivne signed, IN = positiivne signed
- **Mitme sisendfaili tugi:** `transactions.json` + `standing_orders.json` + download-only tuvastus
- **Invariandid (R-01):** valuuta kontroll, value_date kohustuslik, summa parsimine, booking_date valideerimine, summa märk vs suund, counterparty kontroll
- **ML projektsioon (C-02):** BOOKED + PENDING, sorteeritud (account_id, value_date, record_id), row_id täisarvuna
- **LLM projektsioon (C-03):** lühikesed väljanimede (id, d, s, dir, a, c, cp, r), viimased 200 kirjet

### Väljundfailid (`backend/out/`)
- `sv_bundle.json` — kanooniline SVBundle (3 transaktsiooni)
- `ml_projection.csv` — ML projektsioon (3 rida, 12 veergu)
- `llm_context.json` — LLM kontekst lühikeste väljanimedega
- `report.json` — pipeline käivituse aruanne

---

## Projekti struktuur

```text
Adapter/                          # projekti juurkaust (repo)
  README.md                       # projekti ülevaade ja arenduslogi

  spec/                           # deklaratiivsed spetsifikatsioonid
    schemas/                      # JSON Schema failid
      S-00A_berlin_accounts.schema.json   # Berlin AIS kontode sisendi skeema
      S-00B_berlin_transactions.schema.json # Berlin AIS tehingute sisendi skeema
      S-01_sv_schema.json                 # SVBundle väljundi skeema (kanooniline vaheesitus)
      S-02_ml_projection_schema.json      # ML projektsiooni skeema
      S-03_llm_context_schema.json        # LLM konteksti skeema
    contracts/                    # lepingud (transformatsioonireeglid)
      C-01_berlin_to_sv.yaml      # Berlin AIS → SV kaardistus
      C-02_sv_to_ml.yaml          # SV → ML projektsioon
      C-03_sv_to_llm.yaml         # SV → LLM projektsioon
    rulesets/                     # invariandid ja reeglid
      R-01_sv_invariants.yaml     # SV kvaliteedi invariandid (6 reeglit)
    profiles/                     # profiilid
      default.yaml                # vaikimisi profiil (viitab kõigile spec-failidele)

  datasets/                       # testiandmestikud (Berlin AIS JSON)
    D1_public_valid_small/        # happy-path andmestik
      accounts.json               # 1 konto (DE IBAN, EUR)
      transactions.json           # 7 tehingut (booked + pending)
    D4_synth_errors_seed42/       # vigaste andmetega andmestik
      accounts.json
      transactions.json

  backend/                        # Pythoni adapter (andmete töötlemine)
    run_adapter.py                # peamine käivitusfail; käivitab pipeline'i
    requirements.txt              # Pythoni sõltuvused (jsonschema, PyYAML, ...)
    venv/                         # Pythoni virtuaalkeskkond

    adapter/                      # adapteri Pythoni moodul
      __init__.py                 # ekspordib run_pipeline
      pipeline.py                 # täielik pipeline: RAW → SV → ML/LLM → raport

    out/                          # pipeline väljundid (run-kaustadena)
      <timestamp>_<run_id>/       # ühe käivituse kaust
        sv.json                   # kanooniline SVBundle
        report.json               # pipeline käivituse aruanne
        projections/
          ml_v1.csv               # ML projektsioon (CSV)
          llm_context_v1.json     # LLM kontekst (JSON)

    tests/                        # automaattestid
      tests.py                    # 36 happy-path testi (pytest)

  frontend/                       # Vue/JavaScript kasutajaliides / demo
```
---

## Üldine templiit iga olulise täienduse jaoks

```md
## AAAA-KK-PP

### Mida tegin
- ...

### Miks
- ...

### Järgmised sammud
- ...
```

# Adapter / standardiseerimiskiht

Prototüüp loeb Berlin Group / PSD2 AIS stiilis sisendfailid ja teisendab need standardiseeritud vaheesituseks (SV).
SV põhjal tuletatakse deterministlikud projektsioonid (ML CSV ja LLM context JSON) ning koostatakse koondraport.

Normatiivne käitumine on kirjeldatud `spec/` kataloogi versioonitud skeemide, lepingute ja reeglitega.

## Kiirstart (D1 happy path)

Sisend:
- `datasets/D1_public_valid_small/accounts.json`
- `datasets/D1_public_valid_small/transactions.json`

Kasutatav profiil:
- `spec/profiles/default.yaml`

Käivitamine:
```bash
python backend/run_adapter.py \
  --data D1 \
  --out backend/out
```

Väljundid tekivad jooksu-kausta alla (vt Variant A kirjeldust):
- `backend/out/<timestamp>_<run_id>/sv.json`
- `backend/out/<timestamp>_<run_id>/projections/ml_v1.csv`
- `backend/out/<timestamp>_<run_id>/projections/llm_context_v1.json`

---

## Arhitektuur (Variant A)

Valik: **lokaalselt käivitatav modulaarne monoliit**, kus tuumloogika on I/O-st eraldatav (Ports & Adapters), pipeline on sammupõhine ning veamudeliks on kogutud raport.

Lühike arhitektuuri kokkuvõte: [`plans/variant-a-project-structure.md`](plans/variant-a-project-structure.md:1).

Operatiivsed käsud (1 dataset / kõik datasetid / validaator): [`docs/runbook.md`](docs/runbook.md:1).

---

## Runbook

Kõik käivitus- ja valideerimiskäsud on koondatud: [`docs/runbook.md`](docs/runbook.md:1).
