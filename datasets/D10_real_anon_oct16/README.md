# D10_real_anon_oct16

Pärisandmed anonümiseeritud Eesti pangakontolt. Kaks täiskuud (oktoober–november 2016) igapäevaseid tehinguid: toidupoed, kohvikud, transpordimaksed jne. Pending-tehinguid ei ole. Testib, kuidas adapter tuleb toime reaalse, ebaühtlase pangaväljavõttega, kus remittance-tekstid on lühikesed POS-kirjed ja osa väljadest (debtorName jt) puudub.

## Omadused

| Omadus | Väärtus |
|---|---|
| Seed | – (pärisandmed) |
| Kuupäevavahemik | 2016-10-01 – 2016-11-30 |
| Broneeritud (booked) | 101 |
| Ootel (pending) | 0 |
| Oodatav dropitud | 0 |
| Oodatav tulemus | SUCCESS |

## Mida see dataset testib

Reaalse pangaväljavõtte töötlemist. Tehingud on pärit füüsilisest maailmast — summad, kuupäevad ja kirjeldused on ebaühtlased. Kontrollib, et adapter ei dropi ega filtreeri tehinguid ainult seetõttu, et vabateksti väljad on lühikesed või et debtorName puudub. Valideerib samuti, et anonümiseerimiseks kasutatud IBAN ja resourceId läbivad skeemi kontrollid.

## Variatsioonid / süstitud koodid

  (puuduvad)

## Kvaliteedivärava hoiatused

(puuduvad)
