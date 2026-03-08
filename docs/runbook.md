# Runbook: adapteri käivitamine ja artefaktid

See dokument koondab **operatiivsed käsud** (üks dataset, kõik datasetid, valideerimine) ning selgitab, kuhu failid kirjutatakse.

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
  - Kui jätad andmata, kasutatakse vaikimisi `<repo>/.backend/out/`.
- `--target-llm MODEL [MODEL ...]`: LLM mudel(id), millele genereerida projektsioonid.
  - Valikud: `llama3.1-8b-instruct`, `mistral-7b-instruct-v0.3`, `qwen2.5-7b-instruct`
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
      ml_v1.csv                    # baas-ML projektsioon (alati)
      llm_context_v1.json          # baas-LLM kontekst (alati)
      ml_xgboost.csv               # XGBoost-spetsiifiline (kui --target-ml xgboost)
      ml_catboost.csv              # CatBoost-spetsiifiline (kui --target-ml catboost)
      llm_llama3.txt               # Llama 3 prompt (kui --target-llm llama3.1-8b-instruct)
      llm_mistral.txt              # Mistral prompt (kui --target-llm mistral-7b-instruct-v0.3)
      llm_qwen.txt                 # Qwen prompt (kui --target-llm qwen2.5-7b-instruct)
```

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
