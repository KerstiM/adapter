# Compat-kihi kutsekohad (`backend/adapter/`)

> Loodud 2026-02-21.
> Eesmärk: inventuur igast kohast, mis impordib või viitab
> **tagasiühilduvuse ümbrisele** `backend/adapter/pipeline.py`
> (failisüsteemi signatuur `run_pipeline(data_dir, output_dir, ...)`).
> Need tuleb migreerida enne, kui `adapter/` (ainsus) paketi saab eemaldada.

---

## 1. Impordikohad (`from adapter.pipeline import run_pipeline`)

| # | Fail | Rida | Kontekst |
|---|------|------|----------|
| 1 | `backend/run_adapter.py` | 13 | CLI sisenemispunkt |
| 2 | `backend/tests/tests.py` | 24 | Peamine testikomplekt |
| 3 | `scripts/validate_artifacts.py` | 100 | Artefaktide valideerimise abiskript |
| 4 | `scripts/compare_golden.py` | 25 | Golden-failide võrdlusskript |
| 5 | `scripts/export_golden.py` | 31 | Golden-failide ekspordi skript |
| 6 | `scripts/qa/_utils.py` | 151 | QA abifunktsioon |

## 2. Kutsekohad (compat signatuur)

Kõik kutsujad kasutavad failisüsteemipõhist signatuuri:

```python
run_pipeline(data_dir, output_dir, run_id=None, created_at_utc=None) -> dict
```

| # | Fail | Rida(d) | Kasutatav signatuur |
|---|------|---------|---------------------|
| 1 | `backend/run_adapter.py` | 80 | `run_pipeline(data_dir, output_dir)` |
| 2 | `backend/tests/tests.py` | 47, 472–473, 495, 572 | `run_pipeline(DATA_D1, out, ...)` — osad kutsed sisaldavad `run_id` ja `created_at_utc` |
| 3 | `scripts/validate_artifacts.py` | 101 | `run_pipeline(dataset_dir, output_dir)` |
| 4 | `scripts/compare_golden.py` | 102 | `run_pipeline(...)` |
| 5 | `scripts/export_golden.py` | 80 | `run_pipeline(...)` |
| 6 | `scripts/qa/_utils.py` | 156 | `run_pipeline(...)` |

## 3. Dokumentatsiooniviited failile `backend/adapter/pipeline.py`

| # | Fail | Rida(d) | Märkus |
|---|------|---------|--------|
| 1 | `README.md` | — | Funktsionaalsuse nimekiri |
| 2 | `docs/ARENDUSLOGI.md` | — | Raporti struktuuridokumentatsioon |
| 3 | `docs/ARHITEKTUUR.md` | — | Arhitektuuriplaan |

## 4. Sisemine ühendus (ei ole migratsiooni sihtmärk)

`backend/adapter/pipeline.py` ise impordib **adapters** (mitmus) paketist konkreetsed portide teostused:

| Rida | Import |
|------|--------|
| 22 | `from adapters.fs.clock_impl import FixedClock, SystemClock` |
| 23 | `from adapters.fs.dataset_fs import FsDatasetAdapter` |
| 24 | `from adapters.fs.output_fs import FsOutputAdapter` |
| 25 | `from adapters.fs.spec_fs import FsSpecAdapter` |

Need on osa compat-kihist ja kaovad koos sellega.

## 5. Taaseksport

`backend/adapter/__init__.py` taasekspordib `run_pipeline` moodulist `.pipeline`,
seega `from adapter import run_pipeline` töötab samuti (täiendavaid kutsujaid selle vormi jaoks ei leitud).

---

## Kokkuvõte

- **6 faili** impordivad compat-kihist.
- **~10 eraldiseisvat kutsekohta** kasutavad failisüsteemipõhist signatuuri.
- **3 dokumenti** viitavad failile `backend/adapter/pipeline.py` tee kaudu.
- Migreerimine tähendab iga kutsuja ümberlülitamist kasutama `application.pipeline.run_pipeline` otse (pordipõhine signatuur) ja adapterite konstrueerimist kutsumiskohas.
