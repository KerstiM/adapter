# Runbook: adapteri käivitamine ja artefaktid

See dokument koondab **operatiivsed käsud** (üks dataset, kõik datasetid, valideerimine) ning selgitab, kuhu failid kirjutatakse.

## Eeldused

- Käivitad käsud repo juurkaustast.
- Python sõltuvused on paigaldatud.

## CLI (peamised argumendid)

CLI entrypoint on [`backend/run_adapter.py`](backend/run_adapter.py:1).

- `--data` / `-d`: dataset’i nimi või kaust.
  - Toetab:
    - täpset kaustanime `datasets/` all
    - *prefix match* loogikat (nt `D6` sobitub `D6_...`), kus `D1` ei sobitu `D10_...` (underscore fence).
- `--out` / `-o`: väljundi juurkaust.
  - Kui jätad andmata, kasutatakse vaikimisi `<repo>/.backend/out/`.

## 1) Käivita ühe dataset’i peal (artefaktid jäävad alles)

Näide (prefix match):

```bat
python backend\run_adapter.py --data D6 --out backend\out
```

Näide (täpne kaust):

```bat
python backend\run_adapter.py --data datasets\D6_synth_dupes_seed99 --out backend\out
```

## 2) Käivita kõigi dataset’ide peal (artefaktid jäävad alles)

### cmd.exe

```bat
for /d %D in (datasets\D*) do @python backend\run_adapter.py --data %D --out backend\out
```

### PowerShell

```powershell
Get-ChildItem datasets -Directory -Filter 'D*' | ForEach-Object { python backend/run_adapter.py --data $_.FullName --out backend/out }
```

Iga jooks tekitab eraldi run folderi, seega jooksud ei kirjuta üksteist üle.

## 3) End-to-end skeemivaliidatsioon (kõigi dataset’ide peal)

E2E validaator on [`scripts/validate_artifacts.py`](scripts/validate_artifacts.py:1).

Kõik datasetid:

```bat
python scripts\validate_artifacts.py
```

Valitud datasetid (prefix match):

```bat
python scripts\validate_artifacts.py --dataset D1 D2 D3 D4 D5 D6 D7 D8 D9
```

Märkus: validaator jooksutab adapterit **ajutisse kausta** (ei jäta artefakte sinu `backend/out/` alla). Selle eesmärk on kontrollida, kas toodetud artefaktid valideeruvad skeemide vastu.

## 4) Väljundi kaustastruktuur (näide)

Kui `--out backend\\out`, siis tekib tüüpiliselt:

```text
backend/out/
  <timestamp>_<run_id>/
    sv.json
    report.json
    projections/
      ml_v1.csv
      llm_context_v1.json
```

CLI prindib alati:

- `Outcome:` (SUCCESS / PARTIAL_SUCCESS / FAIL)
- `stop_reason:` (miks selline outcome)
- `Run folder:` (täpne kaust, kuhu artefaktid kirjutati)
