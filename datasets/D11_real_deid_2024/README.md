# D11_real_deid_2024

Osaliselt pseudonümiseeritud ja perturbeeritud pärisandmed kahelt seotud Eesti
pangakontolt. Periood: 2024-10-01 – 2024-10-31.

## Omadused

| Omadus | Väärtus |
|---|---|
| Seed | – (pärisandmed) |
| Kuupäevavahemik | 2024-10-01 – 2024-10-31 |
| Kontode arv | 2 |
| Broneeritud – konto 1 | 19 |
| Broneeritud – konto 2 | 129 |
| Ootel (pending) | 0 |
| Oodatav dropitud | 0 |
| Oodatav tulemus | SUCCESS |

## Töötlusaste ja GDPR-staatus

Andmestik on **osaliselt pseudonümiseeritud ja perturbeeritud** pärisandmestik
(ingl *de-identified test dataset*). See **ei vasta** GDPR art 4(5)
pseudonümiseerimise täisnõuetele, kuna puudub eraldi turvaliselt hoitud
võtmehoidla tegelike ja pseudonüümsete identifikaatorite vahel. See **ei ole**
ka anonümiseeritud GDPR mõttes, kuna kvaasi-identifikaatorid (kuupäevad
päevatäpsusega, tehingumustrid, kahe konto omavahelised ristviited, avalikud
IBAN-id ja firmanimed) säilivad ning korrelatsiooniga re-identifitseerimine
jääb teoreetiliselt võimalikuks.

**Kasutatud tehnikad:**

- Pseudonümiseerimine (asendamine): nimed, isiklikud IBAN-id, isikukoodid,
  laenulepingu viited, kaarditerminali numbrid
- Üldistamine: POS-aadressid, perekondlikku konteksti sisaldavad
  remittance-tekstid
- Perturbatsioon: summad ±5–15 %
- Säilitatud (avalik info): kuupäevad, tehingumustrid, kahe konto
  ristviited, avalikud IBAN-id ja firmanimed

Andmestik on mõeldud üksnes arendus- ja testotstarbeks auditeeritava
kvaliteeditõenduse raames (UK2). Andmesubjekt on repositooriumi autor, kes on
avaldamiseks nõusoleku andnud.

## Mida see dataset testib

* PSD2-aegseid reaalset tüüpi tehinguid (2024–2025)
* Kahte seotud kontot, kus ülekanded peegelduvad mõlemas
* Õiget summa-märgikorraldust (debiit negatiivne, kreedit positiivne)
* Kaardimakseid (POS-tekstid), pangaülekandeid, laenumakseid,
  riiklikke toetusi, rahvusvahelisi tehinguid

## Variatsioonid / süstitud koodid

(puuduvad)

## Kvaliteedivärava hoiatused

(puuduvad)
