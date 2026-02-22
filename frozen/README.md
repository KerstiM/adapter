# Külmutatud artefaktid

See kaust sisaldab lukustatud (külmutatud) pipeline artefakte, mida kasutatakse regressioonitestimiseks
ja reprodutseeritavuse kontrollimiseks.

## Kaustastruktuur

```
frozen/
  <versioon>/                    # nt v1.0.0
    spec.lock.json               # Lukustatud spetsifikatsiooni hetktõmmis
    manifest.json                # Oodatavate väljundite manifest
    golden/
      <dataseti_id>/             # Golden-väljundid dataseti kohta
```

## Reeglid

- **`out/`** kaustad (`out/`, `backend/out/`) on **ajutised** ja gitignored.
  Need genereeritakse pipeline skriptidega ja neid ei tohi kunagi commitida.

- **`frozen/<versioon>/`** sisaldab tahtlikult commititud artefakte:
  `spec.lock.json`, `manifest.json` ja `golden/<dataseti_id>/` väljundeid.
  Neid kasutatakse regressioonitestide referentsbaasidena.

- Külmutatud artefakte **uuendatakse ainult tahtlikult**, luues uue versioonkausta
  (nt `frozen/v1.1.0/`). Olemasolevaid versioonikaustasid ei tohiks pärast väljaandmist muuta.
