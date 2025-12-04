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

## Projekti struktuur

```text
Adapter/                     # projekti juurkaust (repo)
  README.md                  # projekti ülevaade ja arenduslogi

  backend/                   # Pythoni adapter (andmete töötlemine)
    run_adapter.py           # peamine käivitusfail; käivitab adapteri pipeline'i
    requirements.txt         # projekti Pythoni sõltuvused (pip freeze väljund)
    venv/                    # Pythoni virtuaalkeskkond (projektispetsiifiline Python + paketid)

    adapter/                 # adapteri Pythoni moodul (äri- ja I/O loogika)
      __init__.py            # teeb kaustast mooduli; ekspordib core-funktsioonid
      core.py                # põhiline äriloogika: Exceli read -> canonical transaction JSON
      io_excel.py            # sisend-I/O: Exceli failide lugemine DataFrame'iks
      io_json.py             # väljund-I/O: valmis JSON-struktuuri salvestamine failiks 

    data/                    # näidisandmed ja adapteri väljundid
      bank.xlsx              # esmane konto väljavõtte Excel (Kaggle/allikas)
      bank 2.xlsx            # teine testfail (sama struktuuriga)
      output.json            # adapteri poolt genereeritud canonical transaction JSON

    tests/                   # automaattestid adapteri jaoks
      tests.py               # pytest testid (Excel -> JSON konversiooni kontroll)

  frontend/                  # Vue/JavaScript kasutajaliides / demo
                             # praegu keskendub projekt backend/adapteri prototüübi realiseerimisele
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
