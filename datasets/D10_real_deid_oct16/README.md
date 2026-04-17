# D10_real_deid_oct16

Osaliselt pseudonümiseeritud ja perturbeeritud pärisandmed ühelt Eesti
pangakontolt. Kaks täiskuud (oktoober–november 2016) igapäevaseid tehinguid:
toidupoed, kohvikud, transpordimaksed jne. Pending-tehinguid ei ole. Testib,
kuidas adapter tuleb toime reaalse, ebaühtlase pangaväljavõttega, kus
remittance-tekstid on lühikesed POS-kirjed ja osa väljadest (debtorName jt)
puudub.

## Omadused

| Omadus | Väärtus |
|---|---|
| Seed | – (pärisandmed) |
| Kuupäevavahemik | 2016-10-01 – 2016-11-30 |
| Broneeritud (booked) | 101 |
| Ootel (pending) | 0 |
| Oodatav dropitud | 0 |
| Oodatav tulemus | SUCCESS |

## Töötlusaste ja GDPR-staatus

Andmestik on **osaliselt pseudonümiseeritud ja perturbeeritud** pärisandmestik
(ingl *de-identified test dataset*). See **ei vasta** GDPR art 4(5)
pseudonümiseerimise täisnõuetele, kuna puudub eraldi turvaliselt hoitud
võtmehoidla tegelike ja pseudonüümsete identifikaatorite vahel. See **ei ole**
ka anonümiseeritud GDPR mõttes, kuna kvaasi-identifikaatorid (kuupäevad
päevatäpsusega, tehingumustrid, avalikud IBAN-id ja firmanimed) säilivad ning
korrelatsiooniga re-identifitseerimine jääb teoreetiliselt võimalikuks.

**Kasutatud tehnikad:**

- Pseudonümiseerimine (asendamine): nimed (4 isikut), isiklikud IBAN-id
  (11 unikaalset kontot), kaardi viimased 4 numbrit (2 kaarti)
- Üldistamine: POS-aadressid (töökoha ja elukoha tuvastamine välistatud),
  perekondlikke viiteid sisaldavad remittance-tekstid
- Perturbatsioon: summad ±5–15 % (palgasumma normaliseeritud)
- Säilitatud (avalik info): kuupäevad, tehingumustrid, ettevõtete nimed,
  avalikud IBAN-id

Andmestik on mõeldud üksnes arendus- ja testotstarbeks auditeeritava
kvaliteeditõenduse raames (UK2). Andmesubjekt on repositooriumi autor, kes on
avaldamiseks nõusoleku andnud.

## Mida see dataset testib

Reaalse pangaväljavõtte töötlemist. Tehingud on pärit füüsilisest maailmast —
summad, kuupäevad ja kirjeldused on ebaühtlased. Kontrollib, et adapter ei dropi
ega filtreeri tehinguid ainult seetõttu, et vabateksti väljad on lühikesed või
et debtorName puudub. Valideerib samuti, et pseudonümiseerimiseks kasutatud
IBAN ja resourceId läbivad skeemi kontrollid.

## Variatsioonid / süstitud koodid

  (puuduvad)

## Kvaliteedivärava hoiatused

(puuduvad)
