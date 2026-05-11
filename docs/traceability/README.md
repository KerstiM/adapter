# Jälgitavus (`docs/traceability/`)

## Eesmärk

See kaust sisaldab repositooriumi detailset, normatiivset nõuete jälgitavust. Lõputöö PDF sisaldab lisas 4 ainult koondvaatelise tabeli (nõue → QS → mõõdik → läbimistingimus → tõendus). Detailne jälgitavus — millised spetsifikatsioonid, testid, artefaktid ja ADR-id iga nõuet katavad — elab repos, et muutuvad seosed oleksid versioonitavad koos koodiga.

## Struktuur

| Fail | Roll |
|------|------|
| [`traceability_matrix.csv`](traceability_matrix.csv) | Põhimatriks — üks rida per nõue (Ä1–Ä3, F1–F6, MF1–MF6). Juhtdokument. |
| [`requirements_to_specs.csv`](requirements_to_specs.csv) | Nõue → spetsifikatsioon (skeem / leping / reeglistik / profiil / LOCK / GOLDEN-MANIFEST). |
| [`requirements_to_tests.csv`](requirements_to_tests.csv) | Nõue → testijuht (TJ-01..TJ-09) ja repo testifail. |
| [`requirements_to_artifacts.csv`](requirements_to_artifacts.csv) | Nõue → tõendusartefakt (sv.json, report.json, projektsioonid, benchmark-logi). |
| [`requirements_to_adr.csv`](requirements_to_adr.csv) | Nõue → arhitektuuriotsus (ADR-01..ADR-08). |
| [`id_dictionary.md`](id_dictionary.md) | ID-perede kokkuvõte: mida Ä/F/MF/QS/SLI/QC/ADR/S/C/R/PROFILE/LOCK/D/TJ tähistavad. |

## Normatiivne vs selgitav

Jälgitavus on **normatiivne jälgitavuskiht**, aga mitte lõplik tehniline tõde. Kui CSV ja kood lähevad lahku, kehtib kood.

- **Tehniline tõde (lõplik allikas)**: repositooriumi spetsifikatsioonifailid (`spec/schemas/`, `spec/contracts/`, `spec/rulesets/`, `spec/profiles/`), testide tegelik käitumine (`backend/tests/`), spetsifikatsioonilukud (`frozen/v*/spec.lock.json`) ja golden SHA-256-d (`frozen/v*/manifest.json`). Käitus ise toodab `sv.json` / `report.json` / projektsioonid vastavalt profiilile.
- **Jälgitavuse CSV-d (see kaust)**: normatiivsed ristviited — ütlevad, millised nõuded, testid, ADR-id ja spetsifikatsioonid on omavahel seotud. Nad on koodi/spetsifikatsioonidega sünkroonis hoidmise kohustuslik layer, aga ei asenda tõenduse tegelikku allikat. CSV ja kood peavad ühtima; erinevuse korral parandatakse CSV-d.
- **`README.md` ja `id_dictionary.md`**: selgitav (mitte-normatiivne) sisu, mis juhatab matriksite ja allikate juurde.

## Relatsioonisõnavarad (normatiivsed loetelud)

CSV-de `relation` veergudes kasutatakse ainult alljärgnevaid väärtusi. Uute väärtuste lisamine nõuab README-s ka siinse loetelu uuendamist.

**`requirements_to_specs.csv`**

| Väärtus | Tähendus |
|---------|----------|
| `NORMATIVE` | Spec defineerib nõude realiseerimise (leping, kaardistus). |
| `VALIDATES_INPUT` | Skeem kontrollib sisendandmeid. |
| `VALIDATES_OUTPUT` | Skeem kontrollib väljundandmeid. |
| `DEFINES_RULES` | Reeglistik defineerib invariandid või veakoodid. |
| `PINS_VERSIONS` | Lukustab versioonid SHA-256 kaudu. |
| `PROFILE_BINDS` | Profiil seob skeemid, lepingud ja reeglistikud käitusele. |
| `REPORT_CONTRACT` | Skeem defineerib raporti kuju. |

**`requirements_to_tests.csv`**

| Väärtus | Tähendus |
|---------|----------|
| `PRIMARY_EVIDENCE` | Peamine automatiseeritud tõend nõudele. |
| `SUPPORTING` | Toetav test (ei ole ainuke tõend, kuid kinnitab). |
| `REGRESSION` | Regressioonikontroll (nt golden-võrdlus). |

**`requirements_to_artifacts.csv`**

| Väärtus | Tähendus |
|---------|----------|
| `PRIMARY` | Peamine väljundartefakt, millelt nõue on loetav. |
| `GOLDEN_REFERENCE` | Etalonfail, mille vastu võrreldakse. |
| `METADATA` | Meta-/auditiinfo (versioonid, SHA-256). |
| `REPORT` | Raportiartefakt. |

**`requirements_to_adr.csv`**

| Väärtus | Tähendus |
|---------|----------|
| `DECIDES` | ADR määrab nõude realiseerimise põhivaliku. |
| `INFLUENCES` | ADR mõjutab nõude realiseerimist kaudselt. |
| `CONSTRAINS` | ADR seab nõudele piirangu. |

## Kuidas jälgitavust uuendada

| Muudatus repos | Uuenda |
|----------------|--------|
| Uus nõue (Ä / F / MF) | `traceability_matrix.csv`, `id_dictionary.md` (tabelis `Nõuded`), vajadusel kõik `requirements_to_*` |
| Uus skeem / leping / reeglistik | `requirements_to_specs.csv`, `frozen/v*/spec.lock.json` (käivita `scripts/qa/build_spec_lock.py`) |
| Uus profiil või profiilimuudatus | `requirements_to_specs.csv`, matriksi veerg `linked_specs` |
| Uus testijuht (TJ) või testifail | `requirements_to_tests.csv` koos repo teega; vajadusel `traceability_matrix.csv` veerg `linked_test_cases` |
| Uus väljundartefakt / projektsioon | `requirements_to_artifacts.csv`, matriksi veerg `evidence_artifacts` |
| Uus ADR | `requirements_to_adr.csv`, matriksi veerg `linked_adr` |
| Uus dataset (D*) | `id_dictionary.md` (tabelis `Andmestikud`), matriksi veerg `linked_datasets`, `frozen/v*/manifest.json` |

Lisaks käivita QA-skeemid:

```sh
python scripts/qa/build_spec_lock.py        # värskendab spec.lock.json
python scripts/qa/run_full_qa.py            # täiskontroll + golden-võrdlus
```

## ID-de kasutus (näide)

Näide nõude `F3` kulgemisest:

1. `traceability_matrix.csv` rida `F3` — `linked_qs=QS3;QS4`, `linked_metrics=SLI2;SLI3;QC2;Gate`, `linked_specs=S-05;R-01;error_catalog;QC_quality_checks`, `linked_test_cases=TJ-04;TJ-05`.
2. `requirements_to_specs.csv` read kirjeldavad, et `S-05` on raportilepingu (`REPORT_CONTRACT`) ja `R-01` defineerib invariandid (`DEFINES_RULES`).
3. `requirements_to_tests.csv` viitab failile [`backend/tests/sli_slo/test_sli_slo.py`](../../backend/tests/sli_slo/test_sli_slo.py) (SLI2/SLI3/QC2/Gate).
4. `requirements_to_artifacts.csv` viitab `report.json` ja `dropped_details[]` väljale raportis.
5. `requirements_to_adr.csv` seob `F3 → ADR-04;ADR-07`.

## Oleku väärtused (`status` veerg matriksis)

| Väärtus | Tähendus |
|---------|----------|
| `ACTIVE` | Kehtiv ja koodiga sünkroonis. |
| `DRAFT` | Veel realiseerimata või dokumenteerimata. |
| `DEPRECATED` | Enam mitte kehtiv; säilitatud ajaloo pärast. |
| `TODO_VERIFY` | Kaardistus vajab käsitsi kontrolli (vt allpool `Teadaolevad ebakõlad`). |

## Teadaolevad ebakõlad (TODO_VERIFY)

Järgnevad punktid selgitavad, kuidas jälgitavus tõlgendab lõputöö koondmudeli ja repo tegeliku seisu suhet.

**Versioonide üldprintsiip:** kui lõputöö tekst ja kood erinevad, kehtib kood. Spetsifikatsioonide praegused versioonid loetakse alati `frozen/v1.1.0/spec.lock.json`-st, mitte lõputöö tekstist.

**Datasettide versioonide ajalugu `frozen/v1.0.0/` vs. `frozen/v1.1.0/`.** Praegune kanooniline nimi on `D10_real_deid_oct16` ja `D11_real_deid_2024` (kasutusel `datasets/` ja `frozen/v1.1.0/golden/` all). Vanem `frozen/v1.0.0/golden/` sisaldab teadlikult varasemat nimetamist `D10_real_anon_oct16` ja `D11_real_anon_2024` — need on lukustatud ajaloolised artefaktid, mida lukustuse põhimõttel enam tagasiulatuvalt ei muudeta. Jälgitavuses kasutatakse kanoonilist lühikest `D*` identifikaatorit ja `requirements_to_artifacts.csv` osutab `frozen/v1.1.0/golden/` kanoonilistele teedele.

**Vaikeprofiili lock vs. `extensions_eval`:** `frozen/v*/spec.lock.json` lukustab tahtlikult ainult vaikeprofiili (`default.yaml`) artefakte. C-05/C-06 ja S-06/S-07 ei ole seal, sest `extensions_eval` on iseseisev eval-profiil, mitte vaikeprofiili laiendus — see on ADR-06 ja MF3 (laienduste lokaalsus) realiseering, mis tõendab, et lisaprojektsioonid ei nihuta vaikeprofiili lukustust.

## Seos lõputöö PDFiga

- Lõputöö lisad 3 (Spetsifikatsioonid), 4 (Jälgitavus), 9 (ADR-id), 10 (Reprodutseerimisjuhend) ja 11 (Mõõdikud) on koondvaated.
- PDF viitab detailse jälgitavuse osas sellele kaustale (`docs/traceability/`).
- Kui PDF ja CSV erinevad, kehtib **repo tõde**, sest koodimuudatused kajastuvad esmalt siin.
