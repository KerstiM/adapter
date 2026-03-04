# D4_synth_errors_seed42

Sihitud veasüstid (E01–E04), mis rikuvad S-00B skeemipiiranguid ja tekitavad ERROR-tasemel droppe. 4 droppi 39 kirjest (10,3%) ületab default.yaml lävendi 5%, seega adapteri tulemus on FAIL.

## Omadused

| Omadus | Väärtus |
|---|---|
| Seed | 42 |
| Kuupäevavahemik | 2024-01-01 – 2024-12-31 |
| Broneeritud (booked) | 34 |
| Ootel (pending) | 5 |
| Oodatav dropitud | 4 |
| Oodatav tulemus | FAIL |

## Mida see dataset testib

Sihitud veasüstid (E01–E04), mis rikuvad S-00B skeemipiiranguid ja tekitavad ERROR-tasemel droppe. 4 droppi 39 kirjest (10,3%) ületab default.yaml lävendi 5%, seega adapteri tulemus on FAIL.

## Variatsioonid / süstitud koodid

  - `E01_INVALID_CURRENCY: currency='EURO' (4 tähemärki) → ERROR DROP`
  - `E02_MISSING_VALUE_DATE: valueDate puudub → ERROR DROP`
  - `E03_UNPARSEABLE_AMOUNT: amount='not_a_number' → ERROR DROP`
  - `E04_EMPTY_CURRENCY: currency='' → ERROR DROP`

## Kvaliteedivärava hoiatused

- D4_synth_errors_seed42: $.transactions.booked[30] valuuta 'EURO' vigane
- D4_synth_errors_seed42: $.transactions.booked[31] valueDate puudub
- D4_synth_errors_seed42: $.transactions.booked[32] summa 'not_a_number' ei vasta mustrile
- D4_synth_errors_seed42: $.transactions.booked[33] valuuta '' vigane
