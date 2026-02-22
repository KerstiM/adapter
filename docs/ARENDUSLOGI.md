# Arenduslogi

Lühike ülevaade tehtud otsustest, valideerimisparandustest ja avatud lõhedest.

---

## 1. Skeemide/lepingute valideerimine ja parandused

### S-05 (raporti skeem) — suurem struktuuriline lahknevus

**Probleem:** S-05 eeldas teistsugust struktuuri kui tegelik `report.json`.

| Aspekt | S-05 eeldas | Tegelik väljund |
|--------|-------------|-----------------|
| `report_schema_version` | Kohustuslik | Puudus |
| `outcome` | Tipptasemel objekt `status` + `stop_reason` | String `summary` sees |
| `issues` | Struktureeritud objektide massiiv | Lihtsate stringide massiiv |
| `by_stage` | Massiiv `{stage, errors, warnings, infos}` | Dict etapi nime järgi |
| `run_flags` | Puudub skeemist | Olemas väljundis |

**Lahendus:** Uuendati **nii pipeline koodi kui ka S-05 skeemi** (lepitusviis):
- Pipeline: outcome enum `FAILED`→`FAIL`, struktureeritud issues, massiivipõhine `by_stage`, lisatud `report_schema_version` ja `stop_reason`.
- S-05: lisatud `run_flags`, `dropped_details`, laiendatud `counts`, eemaldatud `metrics` (prototüübis ei toodeta).

### S-03 (LLM konteksti skeem) — massiiv vs objekt

**Probleem:** S-03 defineeris `type: "object"`, aga mitme konto korral (D3) toodetakse massiiv.

**Lahendus:** S-03 uuendatud `oneOf`-ga — aktsepteerib nii ühte objekti kui massiivi.

### default.yaml — valed skeemiteed

**Probleem:** Profiil viitas `S-00_berlin_accounts.schema.json`-le, tegelikud failid on `S-00A_...` ja `S-00B_...`.

**Lahendus:** Parandatud `default.yaml` teed.

### C-03 leping — aegunud kujukirjeldus

**Probleem:** C-03 viitas `$.accounts[0].*`, eeldades ainult ühte kontot.

**Lahendus:** Uuendatud C-03 dokumenteerima `cardinality` reegel ja kasutama `@current_account.*`.

### Valideerimistulemused (pärast parandusi)

6 datasetti × 6 artefakti = 36 valideerimist:
- **35 PASS** — kõik artefaktid valideeruvad skeemide vastu
- **1 oodatud FAIL** — D4 `transactions.json` vs S-00B (tahtlikult vigane sisend)

---

## 2. Lõhed (target → current)

### Lõhe 1: sõltuvuspiirid (impordireeglid)
- `domain` impordid peavad olema "puhtad" (ei failisüsteemi, ei adaptereid).
- **Staatus:** tehtud. Arhitektuuritest `test_import_boundaries.py` kontrollib.

### Lõhe 2: kogutud raport kui keskne artefakt
- Raport peab olema pipeline keskne väljund, mitte "kirjutame faili lõpus".
- **Staatus:** tehtud. Outcome otsus tugineb raportile + poliitikale.

### Lõhe 3: pipeline nähtav application-kihis
- Pipeline sammud peavad olema eraldi ja puhtad (I/O portide taga).
- **Staatus:** tehtud. `application/pipeline.py` sisaldab 7-sammulise orkestreerimise.

### Lõhe 4: portid on päris portid
- Portide API räägib kontseptsioonidest, mitte path'idest.
- **Staatus:** tehtud. `ports/*` ei kasuta `Path` ega failisüsteemi.

### Lõhe 5: testide kihistus
- Unit/contract/E2E jaotus peab olema sisuliselt korrektne.
- **Staatus:** tehtud. Unit-testid kasutavad fake-porte, E2E kasutab päris adaptereid.

### Lõhe 6: golden/regressioonitestid determinismile
- Determinismi lubadus peab olema kinnitatud golden-artefaktide võrdlusega.
- **Staatus:** tehtud. `frozen/v1.0.0/golden/` + `scripts/qa/verify_goldens.py`.

---

## 3. Muudetud failid (kokkuvõte)

| Fail | Muudatus |
|------|----------|
| `backend/application/pipeline.py` | Raporti struktuur: outcome enum, struktureeritud issues, massiivipõhine by_stage |
| `backend/run_adapter.py` | Struktureeritud issues'te kuvamine |
| `spec/schemas/S-05_collected_report_schema.json` | Täielik ümberkirjutus |
| `spec/schemas/S-03_llm_context_schema.json` | Lisatud oneOf (objekt / massiiv) |
| `spec/contracts/C-03_sv_to_llm.yaml` | Dokumenteeritud mitme konto kardinaalsus |
| `spec/profiles/default.yaml` | Parandatud S-00A/S-00B failiteed |
