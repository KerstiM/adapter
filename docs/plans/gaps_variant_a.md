# Variant A gap list (Target → Current)

Eesmärk: hoida “target” ja “current” ausalt koos. See on lühike tööriist, mis kirjeldab lõhed ja lõpetamise kriteeriumid.

## Target statement

- Variant A: lokaalne modulaarne monoliit, Ports & Adapters sõltuvuspiirid, application-kihis sammupõhine pipeline, esmaklassiline collected report.

## Current state (lühidalt)

- Loogika + I/O on suuresti koondunud ühte pipeline-moodulisse.
- Spec (schemas/contracts/rulesets/profile) on olemas ja versioonitav.
- E2E valideerimine on olemas skriptina.

## Gap 1: sõltuvuspiirid (import reegel)

- Gap: `domain` impordid peavad olema “puhad” (ei failisüsteemi, ei adapters).
- Acceptance:
  - lisatud arhitektuuri test, mis tuvastab keelatud importid `domain`-is
  - application impordib ainult `domain + ports`

## Gap 2: collected report kui keskne artefakt

- Gap: report ei tohi olla “kirjutame faili lõpus”, vaid olema pipeline’i keskne väljund.
- Acceptance:
  - outcome otsus tugineb ainult `report + policy`
  - etapid tagastavad report events

## Gap 3: pipeline nähtav application-kihis

- Gap: pipeline sammud peavad olema eraldi ja puhtad (I/O portide taga).
- Acceptance:
  - `application/pipeline.py` sisaldab orkestreerimist (7 sammu)
  - igal sammul on testid

## Gap 4: ports on päris portid

- Gap: portide API räägib kontseptsioonidest, mitte path’idest.
- Acceptance:
  - `ports/*` ei kasuta `Path` ega failisüsteemi
  - fs detailid ainult `adapters/fs/*`

## Gap 5: testide kihistus

- Gap: unit/contract/e2e jaotus peab olema sisuliselt korrektne.
- Acceptance:
  - unit-testid ei impordi adapters
  - e2e testid jooksutavad pipeline’i päris dataset’ide peal

## Gap 6: golden/regressioonitestid determinismile

- Gap: determinismi lubadus peab olema kinnitatud golden-artefaktide võrdlusega.
- Acceptance:
  - lisatud testikategooria `regression/` või `e2e/golden/`
  - golden-id (nt `golden/`) on seotud testidega ja CI kontrollib, et väljund ei muutuks märkamatult

Staatus: TODO (täida jooksvalt koos refaktoriga)
