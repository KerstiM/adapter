# D5_synth_edges_seed99

Skeemikehtivad piiripealsed juhud, mis testivad piiritingimusi: nullsumma, suur summa, täisarvuline summa, märgikonventsioonid, samad kuupäevad, pikk makseselgitus ja puuduv vastaspool (INV-10 WARN).

## Omadused

| Omadus | Väärtus |
|---|---|
| Seed | 99 |
| Kuupäevavahemik | 2024-01-01 – 2024-12-31 |
| Broneeritud (booked) | 28 |
| Ootel (pending) | 5 |
| Oodatav dropitud | 0 |
| Oodatav tulemus | PARTIAL_SUCCESS |

## Mida see dataset testib

Skeemikehtivad piiripealsed juhud, mis testivad piiritingimusi: nullsumma, suur summa, täisarvuline summa, märgikonventsioonid, samad kuupäevad, pikk makseselgitus ja puuduv vastaspool (INV-10 WARN).

## Variatsioonid / süstitud koodid

  - `EDGE01_ZERO_AMOUNT: amount='0.00' — kehtiv, aga semantiliselt ebatavaline`
  - `EDGE02_LARGE_AMOUNT: amount='9999999.999' — maksimaalne täpsus`
  - `EDGE03_INTEGER_AMOUNT: amount='1' — kehtiv mustri ^-?\d+(\.\d{1,3})?$ järgi`
  - `EDGE04_NEGATIVE_OUT: amount='-50.00' + creditorName → OUT, märk vastab, INV-05 puudub`
  - `EDGE05_POSITIVE_IN: amount='100.50' + debtorName → IN, INV-05 puudub`
  - `EDGE06_SAME_DATES: bookingDate == valueDate == 2024-07-10`
  - `EDGE07_LONG_REMITTANCE: 307 tähemärki — kehtiv, LLM projektsioon kärbib 160-le`
  - `EDGE08_NO_COUNTERPARTY: vastaspool puudub → suund märgi järgi, INV-10 WARN`

## Kvaliteedivärava hoiatused

(puuduvad)
