# D7 — Püsikorraldused (seed 77)

Fookusega dataset püsikorralduste / INFORMATION tehingute kaardistuse valideerimiseks
`nextExecutionDate` fallback'i kaudu.

## Sisu

| Fail                   | Kirjeldus                                             |
|------------------------|-------------------------------------------------------|
| accounts.json          | Üks EUR arvelduskonto                                 |
| transactions.json      | 1 broneeritud tehing, tühi ootel massiiv              |
| standing_orders.json   | 3 INFORMATION püsikorralduse kirjet (vt allpool)      |

## Püsikorralduse kirjed

| # | creditorName          | valueDate  | nextExecutionDate | Oodatav value_date |
|---|-----------------------|------------|-------------------|--------------------|
| 1 | Stadtwerke Berlin     | _(puudub)_ | 2025-02-01        | 2025-02-01 (fallback nextExecutionDate'ile) |
| 2 | Vonovia SE            | 2025-02-01 | 2025-03-01        | 2025-02-01 (valueDate on eelistatud)        |
| 3 | Allianz Versicherung  | _(puudub)_ | 2025-04-01        | 2025-04-01 (fallback nextExecutionDate'ile) |

## Oodatav pipeline tulemus

- **Tulemus**: `SUCCESS` või `PARTIAL_SUCCESS`
- **accounts_total**: 1
- **transactions_total**: 4 (1 broneeritud + 3 information)
- **transactions_emitted_sv**: 4
- **transactions_dropped**: 0

Veasüste ei ole — kõik tehingud peaksid edukalt kaardistuma. Kirjed 1 ja 3
harjutavad `coalesce(valueDate, nextExecutionDate)` fallback-reeglit
INFORMATION staatusega tehingute jaoks; kirje 2 kinnitab, et `valueDate` on eelistatud, kui olemas.

INFORMATION tehingud jäetakse välja ML ja LLM projektsioonidest (C-02 / C-03
filtreerivad ainult BOOKED + PENDING), seega projektsioonid sisaldavad ainult üht
broneeritud tehingut.
