# QA skriptid

Adapteri pipeline end-to-end kvaliteedikontroll.

## `run_full_qa.py` — QA peamine sisenemispunkt

Jooksutab kõik kontrollietapid järjest:

1. **Spetsifikatsiooni terviklikkus** — profiili viited, failide olemasolu, versioonivälad
2. **Dataseti sisendi valideerimine** — skeemi- ja semantilised kontrollid toorsisenditel
3. **Pipeline väljundi valideerimine** — skeemivalideerimine + artefaktide ristkontroll
4. **Golden-snapshotide võrdlus** — SHA-256 võrdlus külmutatud goldenitega
5. **Determinismi suitsukontroll** — pipeline toodab kordusjooksul identse väljundi

### Kiirkäivitus

```bash
# Kõik datasetid (repo juurkaustast)
python scripts/qa/run_full_qa.py

# Üks dataset
python scripts/qa/run_full_qa.py --dataset D1_public_valid_small

# Mitu datasetti
python scripts/qa/run_full_qa.py --dataset D1,D2

# Kiire režiim (ainult D1 + D3)
python scripts/qa/run_full_qa.py --fast

# Ilma golden-võrdluseta (ainult valideerimine)
python scripts/qa/run_full_qa.py --skip-golden
```

### Windows PowerShell

```powershell
# Kõik datasetid
python scripts\qa\run_full_qa.py

# Üks dataset
python scripts\qa\run_full_qa.py --dataset D1_public_valid_small

# Kiire režiim
python scripts\qa\run_full_qa.py --fast

# Ilma golden-võrdluseta
python scripts\qa\run_full_qa.py --skip-golden
```

### Väljundikoodid

| Kood | Tähendus |
|------|----------|
| `0` | Kõik kontrollid läbitud |
| `1` | Üks või enam kontrolli ebaõnnestus |

### Väljundi formaat

```
SPEC: PASS
DATASETS: PASS/FAIL
OUTPUTS: PASS/FAIL
GOLDENS: PASS/FAIL
DETERMINISM: PASS/FAIL
```

Ebaõnnestumiste korral kuvatakse kompaktsed dataseti- ja failipõhised üksikasjad.

## Muud QA skriptid

| Skript | Eesmärk |
|--------|---------|
| `build_spec_lock.py` | Genereerib `frozen/v1.0.0/spec.lock.json` profiilist |
| `freeze_goldens.py` | Külmutab pipeline väljundid kausta `frozen/v1.0.0/golden/` |
| `verify_goldens.py` | Kontrollib, et külmutatud goldenid on endiselt reprodutseeritavad |

### Eeldused

```bash
pip install jsonschema pyyaml
```
