# D6_synth_dupes_seed99

Testib INV-09 duplikaat-record_id tuvastust. Sisaldab 3 täpset duplikaati (samad räsisisendid → sama record_id → dropitakse INV-09 WARN-iga, jäetakse alles esimene deterministlikult) ja 2 peaaegu-duplikaati (erinev summa või makseselgitus → erinev record_id → jäetakse alles). Adapter peab andma tulemuse PARTIAL_SUCCESS 3 INV-09 WARN-iga.

## Omadused

| Omadus | Väärtus |
|---|---|
| Seed | 99 |
| Kuupäevavahemik | 2024-01-01 – 2024-12-31 |
| Broneeritud (booked) | 21 |
| Ootel (pending) | 3 |
| Oodatav dropitud | 3 |
| Oodatav tulemus | PARTIAL_SUCCESS |

## Mida see dataset testib

Testib INV-09 duplikaat-record_id tuvastust. Sisaldab 3 täpset duplikaati (samad räsisisendid → sama record_id → dropitakse INV-09 WARN-iga, jäetakse alles esimene deterministlikult) ja 2 peaaegu-duplikaati (erinev summa või makseselgitus → erinev record_id → jäetakse alles). Adapter peab andma tulemuse PARTIAL_SUCCESS 3 INV-09 WARN-iga.

## Variatsioonid / süstitud koodid

  - `DUP01_EXACT: booked[0] täpne koopia (transactionId=TX00000013) → INV-09 DROP`
  - `DUP02_EXACT: booked[0] teine koopia (transactionId=TX00000013) → INV-09 DROP`
  - `DUP03_EXACT: booked[1] täpne koopia (transactionId=TX00000002) → INV-09 DROP`
  - `NEAR01_DIFF_AMOUNT: sama txId=TX00000007, summa erineb → erinev record_id, jäetakse alles`
  - `NEAR02_DIFF_REMITTANCE: sama txId=TX00000019, makseselgitus erineb → erinev record_id, mõlemad jäävad`

## Kvaliteedivärava hoiatused

(puuduvad)
