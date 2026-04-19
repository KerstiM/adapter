# Runbook: adapteri käivitamine ja artefaktid

See dokument koondab **operatiivsed käsud** (üks dataset, kõik datasetid, valideerimine) ning selgitab, kuhu failid kirjutatakse.

## Käivitusrežiimid lühidalt

Adapter toetab kolme tüüpi jookse. Kõigi puhul tekib eraldi
`<timestamp>_<run_id>/` kaust ja igal juhul toodetakse `sv.json` ja
`report.json`; erinevus on `projections/` sisus.

| Režiim | Käsk (näide) | Lisanduvad failid kaustas `projections/` |
|---|---|---|
| **Baas (mudelita)** | `python backend/run_adapter.py --data D1` | `ml_v1.csv`, `llm_context_v1.json` |
| **Mudelitega** | `python backend/run_adapter.py --data D1 --target-llm llama3.1-8b-instruct --target-ml xgboost` | baas + mudelispetsiifilised vormindused (`llm_context_v1_<perekond>.json`, `ml_v1_<mudel>.json`) |
| **Laiendatud profiil** | `python backend/run_adapter.py --data D1 --profile extensions_eval` | baas + `stats_v1.json`, `monthly_balance_v1.json` |

> **NB.** Adapter ei kutsu välja LLM-i ega ML-mudelit — see vaid genereerib
> deterministlikud sisendfailid (`projections/`), mida saab anda välistele
> mudelitele. `--target-llm` ja `--target-ml` valivad **vormingu** (vt
> [`spec/contracts/C-04_model_formatters.yaml`](../spec/contracts/C-04_model_formatters.yaml)),
> mitte ei käivita inferentsi.

Allpool on iga režiimi täpsem käivitusjuhend ja jaotises **4** kogu
väljundi kaustastruktuur ning lipp→fail tabel.

## Eeldused

- Python sõltuvused on paigaldatud (`pip install -r backend/requirements.txt`).
- `--out` suhteline tee laheneb **repo juure** suhtes (mitte CWD suhtes), seega käsud töötavad ükskõik millisest kaustast.

## CLI (peamised argumendid)

CLI entrypoint on [`backend/run_adapter.py`](backend/run_adapter.py:1).

- `--data` / `-d`: dataset'i nimi või kaust.
  - Toetab:
    - täpset kaustanime `datasets/` all
    - *prefix match* loogikat (nt `D6` sobitub `D6_...`), kus `D1` ei sobitu `D10_...` (underscore fence).
- `--out` / `-o`: väljundi juurkaust (suhteline repo juure suhtes).
  - Kui jätad andmata, kasutatakse vaikimisi `<repo>/.pipeline_out/` (gitignoreeritud).
- `--profile` / `-p`: jooksuprofiil. Vaikimisi: `default`.
  - `default` — baasskeemid + lepingud (S-00A..S-05, C-01..C-04, R-01). Lisaprojektsioone ei luba.
  - `extensions_eval` — lisab S-06, S-07, C-05, C-06 ja lubab `extra_projections` (statistika + kuubilanss).
- `--target-llm MODEL [MODEL ...]`: LLM mudel(id), millele genereerida projektsioonid.
  - Valikud: `llama3.1-8b-instruct`, `mistral-7b-instruct-v0.3`, `qwen2.5-7b-instruct`, `gemma-2-2b-it`
- `--target-ml MODEL [MODEL ...]`: ML mudel(id), millele genereerida projektsioonid.
  - Valikud: `xgboost`, `catboost`
- `--llm-preamble TEXT`: LLM süsteemne preamble (ülekirjutab profiili seadistuse).

CLI mudeli-argumendid ülekirjutavad profiili `target_models` sektsiooni. Kui mudeleid ei vali, genereeritakse ainult baas-projektsioonid (`ml_v1.csv`, `llm_context_v1.json`).

## 1) Käivita ühe dataset'i peal (artefaktid jäävad alles)

### PowerShell / bash

```powershell
python backend/run_adapter.py --data D6 --out backend/out
```

Näide (täpne kaust):

```powershell
python backend/run_adapter.py --data datasets/D6_synth_dupes_seed99 --out backend/out
```

### cmd.exe

```bat
python backend\run_adapter.py --data D6 --out backend\out
```

## 1a) Käivita konkreetsete mudelitega

### Üks LLM ja üks ML mudel

```bash
python backend/run_adapter.py --data D1 --target-llm llama3.1-8b-instruct --target-ml xgboost
```

### Mitu mudelit korraga

```bash
python backend/run_adapter.py --data D1 \
  --target-llm llama3.1-8b-instruct mistral-7b-instruct-v0.3 qwen2.5-7b-instruct \
  --target-ml xgboost catboost
```

### Kohandatud LLM preamble

```bash
python backend/run_adapter.py --data D1 \
  --target-llm llama3.1-8b-instruct \
  --llm-preamble "Analüüsi pangatehinguid ja tuvasta anomaaliad."
```

### Laiendatud profiil (statistika + kuubilanss)

```bash
python backend/run_adapter.py --data D1 --profile extensions_eval --out backend/out
```

### PowerShell

```powershell
python backend/run_adapter.py --data D1 --target-llm llama3.1-8b-instruct mistral-7b-instruct-v0.3 --target-ml xgboost catboost
```

### cmd.exe

```bat
python backend\run_adapter.py --data D1 --target-llm llama3.1-8b-instruct --target-ml xgboost
```

## 2) Käivita kõigi dataset'ide peal (artefaktid jäävad alles)

### PowerShell

```powershell
Get-ChildItem datasets -Directory -Filter 'D*' |
  ForEach-Object { python backend/run_adapter.py --data $_.Name --out backend/out }
```

### cmd.exe

```bat
for /d %D in (datasets\D*) do @python backend\run_adapter.py --data %D --out backend\out
```

### bash / zsh

```bash
for d in datasets/D*/; do python backend/run_adapter.py --data "$d" --out backend/out; done
```

Iga jooks tekitab eraldi run folderi, seega jooksud ei kirjuta üksteist üle.

## 3) End-to-end skeemivaliidatsioon (kõigi dataset'ide peal)

E2E validaator on [`scripts/validate_artifacts.py`](scripts/validate_artifacts.py:1).

Kõik datasetid:

```powershell
python scripts/validate_artifacts.py
```

Valitud datasetid (prefix match):

```powershell
python scripts/validate_artifacts.py --dataset D1 D2 D3 D4 D5 D6 D7 D8 D9 D10
```

Märkus: validaator jooksutab adapterit **ajutisse kausta** (ei jäta artefakte sinu `backend/out/` alla). Selle eesmärk on kontrollida, kas toodetud artefaktid valideeruvad skeemide vastu.

## 4) Väljundi kaustastruktuur (näide)

Kui `--out backend/out`, siis tekib tüüpiliselt:

```text
backend/out/
  <timestamp>_<run_id>/
    sv.json
    report.json
    projections/
      ml_v1.csv                       # baas-ML projektsioon (alati)
      llm_context_v1.json             # baas-LLM kontekst (alati)
      ml_v1_xgboost.json              # XGBoost-vorming (kui --target-ml xgboost)
      ml_v1_catboost.json             # CatBoost-vorming (kui --target-ml catboost)
      llm_context_v1_llama3.json      # Llama 3 vorming (kui --target-llm llama3.1-8b-instruct)
      llm_context_v1_mistral.json     # Mistral vorming (kui --target-llm mistral-7b-instruct-v0.3)
      llm_context_v1_qwen.json        # Qwen vorming (kui --target-llm qwen2.5-7b-instruct)
      llm_context_v1_gemma.json       # Gemma 2 vorming (kui --target-llm gemma-2-2b-it)
      stats_v1.json                   # C-05 statistika (kui --profile extensions_eval)
      monthly_balance_v1.json         # C-06 kuubilanss (kui --profile extensions_eval)
```

### Lipp → tekkiv fail (kokkuvõte)

| Lipp / profiil | Tekkiv fail kaustas `projections/` |
|---|---|
| (ilma mudelilippudeta) | `ml_v1.csv`, `llm_context_v1.json` |
| `--target-ml xgboost` | `ml_v1_xgboost.json` |
| `--target-ml catboost` | `ml_v1_catboost.json` |
| `--target-llm llama3.1-8b-instruct` | `llm_context_v1_llama3.json` |
| `--target-llm mistral-7b-instruct-v0.3` | `llm_context_v1_mistral.json` |
| `--target-llm qwen2.5-7b-instruct` | `llm_context_v1_qwen.json` |
| `--target-llm gemma-2-2b-it` | `llm_context_v1_gemma.json` |
| `--profile extensions_eval` | `stats_v1.json`, `monthly_balance_v1.json` |

Mitme mudeli korraga andmisel (`--target-llm A B C`) tekib iga valitud
mudeli kohta üks fail. Mudelilipud ei muuda baasprojektsioone — `ml_v1.csv`
ja `llm_context_v1.json` kirjutatakse alati.

CLI prindib alati:

- `Outcome:` (SUCCESS / PARTIAL_SUCCESS / FAIL)
- `stop_reason:` (miks selline outcome)
- `Run folder:` (täpne kaust, kuhu artefaktid kirjutati)
- `Target LLM:` / `Target ML:` (kui mudelid on valitud)

## 5) API kaudu mudeli valimine

API server (`python -m entrypoints.api`) toetab mudeli valikut `POST /api/run` päringus:

```bash
curl -X POST http://localhost:5000/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "datasetId": "D1",
    "targetLlm": ["llama3.1-8b-instruct", "mistral-7b-instruct-v0.3"],
    "targetMl": ["xgboost"],
    "llmPreamble": "Analüüsi pangatehinguid."
  }'
```

Toetatud väljad:
- `targetLlm` — string või string[] — LLM mudeli ID-d
- `targetMl` — string või string[] — ML mudeli ID-d
- `llmPreamble` — string — LLM süsteemne preamble

Kui mudeli väljad puuduvad, kasutatakse profiili vaikeseadistust (või genereeritakse ainult baas-projektsioonid).
