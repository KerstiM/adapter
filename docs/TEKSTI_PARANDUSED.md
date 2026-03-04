# Tekst vs kood: parandussoovitused

Selle dokumendi lõi koodi ja bakalaureusetöö teksti vastavuse analüüs.
Allpool on konkreetsed tekstiparandused LaTeX-failides.

---

## B1. "reeglipõhine" projektsioon — koodis puudub

**Asukoht**: `\section{Tehinguandmete standardiseerimine}` (lit-data-standardization)

**Praegune tekst**:
```latex
tuletatakse sellest tarbijaspetsiifilised projektsioonid (reeglipõhine, ML, LLM)
```

**Parandus** (variant A — eelistatud, kui reeglipõhine tarbija loeb SV-d otse):
```latex
tuletatakse sellest tarbijaspetsiifilised projektsioonid (ML, LLM);
reeglipõhine tarbija saab kasutada SV-d otse, ilma eraldi projektsioonita
```

**Parandus** (variant B — kui reeglipõhine projektsioon on skoobist välja jäetud):
```latex
tuletatakse sellest tarbijaspetsiifilised projektsioonid (ML, LLM)
```

**Põhjus**: Koodis on ainult kaks projektsiooni: C-02 (SV→ML CSV) ja C-03 (SV→LLM JSON).
Reeglipõhist projektsiooni (nt C-04) ei eksisteeri. Ülesande püstitus (sec:intro-task)
ütleb korrektselt "vähemalt kahe tarbijavaate jaoks (ML, LLM)".

---

## B2. D9 andmestik — koodis olemas, tekstis mainimata

**Asukoht**: `\section{Hindamisprotokoll}` (sec:method-evaluation), viimane lõik

**Praegune tekst**:
```latex
Hindamisel kasutatakse deterministliku generaatoriga loodud testandmestikke (D1--D7),
mille seed, manifest ja kontrollsummad on lisas~\ref{app:testandmestikud}.
Lisaks kasutatakse koormustesti andmestikku D8 (10\,000 tehingut)...
```

**Parandus**:
```latex
Hindamisel kasutatakse deterministliku generaatoriga loodud testandmestikke (D1--D7),
mille seed, manifest ja kontrollsummad on lisas~\ref{app:testandmestikud}.
Lisaks kasutatakse koormustesti andmestikku D8 (10\,000 tehingut),
et kontrollida jõudluse mõistlikkuse skaleerumist väljaspool MF6 standardset piiri,
ning andmestikku D9 (1\,000 tehingut, seed\,=\,9) jõudluse mõistlikkuse kontrolli
standardtestina.
```

**Põhjus**: Koodis on `datasets/D9_synth_perf_seed9/` ja `frozen/v1.0.0/manifest.json`
sisaldab D9 kirjet (koos golden hashidega). Tekst peab kajastama kõiki testandmestikke.

---

## B3. "ajatsoonide normaliseerimine" — täpsustamine

**Asukoht**: `\section{Ülesande püstitus}` (sec:intro-task)

**Praegune tekst**:
```latex
tagatakse determinism (järjekord, ümardus, ajatsoonide normaliseerimine, stabiilne serialiseerimine)
```

**Parandus**:
```latex
tagatakse determinism (järjekord, kanoonilised arvukujud, UTC-konventsioon metaandmetele, stabiilne serialiseerimine)
```

**Põhjus**: Kood ei tee aktiivset ajavööndi teisendust (nt EET→UTC).
Sisendkuupäevad on ajavööndita ISO kuupäevad (YYYY-MM-DD);
metaandmete ajatemplid (nt `created_at_utc`) on alati UTC-s (Z-sufiks).
Termin "ajatsoonide normaliseerimine" jätab mulje aktiivsest teisendusest.

---

## B4. "ümardus" — kood normaliseerib kujutust, ei ümarda

**Asukoht**: sama lause kui B3

**Parandus**: vt B3 ülal — "ümardus" asendatud terminiga "kanoonilised arvukujud"

**Põhjus**: `c01_raw_to_sv.py:_decimal_str()` kasutab `Decimal.normalize()` ja
`format(d, "f")`, mis eemaldab lõpu-nullid ja väldib teaduslikku notatsiooni.
See on kanooniline esituse normaliseerimine, mitte ümardamine kindlale komakohtade arvule.

---

## B5. SLI-5 — kahetähenduslik (versioonid vs laiendatavus)

**Asukoht**: tabel `tab:uk-to-evidence` ja SLI/SLO lisa

**Praegune tekst** (tabelis):
```
UK3 | ... | SLI5 (tase 1--2) | Evolutsiooniharjutus ...
```

**Koodis** (`test_sli_slo.py`):
SLI-5 testib versiooni metaandmete olemasolu raportis
(sv_schema_version, mapping_version, ruleset_version, adapter_version).
SLO: 100% jooksudest sisaldab kõiki versiooniväljasid.

**Probleem**: UK3 tabelis viidatakse SLI5-le kui laiendatavuse pingutustaseme mõõdikule
(tase 1–2), kuid koodis on SLI-5 defineeritud kui versiooni metaandmete olemasolu
kontroll. Need on eri mõõdikud.

**Soovitus** (variant A): Lisa SLI/SLO tabelisse eraldi rida laiendatavuse jaoks
(nt SLI-7), mida hinnatakse evolutsiooniharjutusega. SLI-5 jääb versiooni
metaandmete kontrolliks.

**Soovitus** (variant B): Defineeri SLI-5 kaheosalisena:
(a) versiooni metaandmete olemasolu (automaatne test),
(b) laiendatavuse pingutustase (manuaalne evolutsiooniharjutus).

---

## B6. manifest.json — "FAILED" → "FAIL" (PARANDATUD KOODIS)

**Staatus**: Juba parandatud failis `frozen/v1.0.0/manifest.json`.

Muudatus: `"expected_outcome": "FAILED"` → `"expected_outcome": "FAIL"`
D4_synth_errors_seed42 kirjes.

Pipeline `determine_outcome()` tagastab `"FAIL"` (ilma D-ta),
seega manifest pidi kasutama sama väärtust.

---

## B7. N=5 determinismijooksud — info

**Olukord**: Tekst ütleb N=5 kordusjooksu. Koodis:
- `tests.py:TestDeterminism` — **N=5** (integratsioonitestis) ✅
- `test_sli_slo.py:TestSLI4Determinism` — N=2 (kergem SLI kontroll)
- `scripts/qa/run_full_qa.py:check_determinism` — N=2 (QA smoke check)

**Soovitus**: Tekst on korrektne viidates integratsioonitestile. Kui soovid täpsustada,
lisa: "Determinismi kontrollib integratsioonitesti `TestDeterminism` klassiga (N=5);
SLI/SLO kiirtest kasutab N=2."

---

## Kokkuvõte

| # | Tüüp | Staatus |
|---|-------|---------|
| B1 | Teksti täpsustus | Vajab muutmist LaTeX-is |
| B2 | Teksti täiendus | Vajab muutmist LaTeX-is |
| B3 | Teksti täpsustus | Vajab muutmist LaTeX-is |
| B4 | Teksti täpsustus | (sama lause kui B3) |
| B5 | SLI definitsioon | Vajab muutmist LaTeX-is |
| B6 | Koodiviga | **Parandatud** |
| B7 | Info | Valiidne, valikuline täpsustus |
