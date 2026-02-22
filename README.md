# Adapter / standardiseerimiskiht

Prototüüp loeb Berlin Group / PSD2 AIS stiilis sisendfailid ja teisendab need standardiseeritud vaheesituseks (SV).
SV põhjal tuletatakse deterministlikud projektsioonid (ML CSV ja LLM context JSON) ning koostatakse koondraport.

Normatiivne käitumine on kirjeldatud `spec/` kataloogi versioonitud skeemide, lepingute ja reeglitega.

## Kiirkäivitus

```bash
# Eeldused: Python 3.10+, sõltuvused paigaldatud
cd backend && pip install -r requirements.txt

# Üks dataset (prefix-match: D1 → D1_public_valid_small)
python backend/run_adapter.py --data D1 --out backend/out

# Kõik datasetid
for d in datasets/D*; do python backend/run_adapter.py --data "$d" --out backend/out; done
```

CLI argumendid:
- `--data / -d` — dataseti nimi (nt `D1`, `D4`) või kaustatee. Vaikimisi: `D1_public_valid_small`.
- `--out / -o` — väljundi juurkaust. Vaikimisi: `<repo>/.backend/out/`.

Väljund tekib jooksukausra alla:

```
<out>/<timestamp>_<run_id>/
    sv.json                          # kanooniline SVBundle
    report.json                      # koondraport (outcome, issues, counts)
    projections/
        ml_v1.csv                    # ML projektsioon
        llm_context_v1.json          # LLM kontekst
```

Täpsem käivitusjuhend: [`docs/runbook.md`](docs/runbook.md).

## Testide käivitamine

```bash
cd backend && python -m pytest tests/ -v
```

Täpsem testistrateegia: [`docs/TESTIMINE.md`](docs/TESTIMINE.md).

## Dokumentatsioon

| Dokument | Kirjeldus |
|----------|-----------|
| [`docs/ARHITEKTUUR.md`](docs/ARHITEKTUUR.md) | Ports & Adapters arhitektuur, pipeline, failipuu |
| [`docs/ARENDUSLOGI.md`](docs/ARENDUSLOGI.md) | Tehtud otsused, valideerimisparandused, lõhed |
| [`docs/TESTIMINE.md`](docs/TESTIMINE.md) | Testiklassid, käivitamisjuhised |
| [`docs/SPETSIFIKATSIOONID.md`](docs/SPETSIFIKATSIOONID.md) | Skeemide, lepingute ja reeglistike indeks |
| [`docs/runbook.md`](docs/runbook.md) | Operatiivsed käivitamiskäsud |
