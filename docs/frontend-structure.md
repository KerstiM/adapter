# Frontend vaate kaardistus (Frontend Structure Map)

## Ülevaade

- **Raamistik**: Vue 3 (Composition API, `<script setup>`)
- **Ehitustööriist**: Vite 7.1.11
- **Ruuter**: vue-router 4.6.3 (üks marsruut: `/` → Dashboard)
- **Juurkaust**: `frontend/vue-project/`

---

## 1. Peamine ekraan – DashboardView

**Fail**: `src/views/DashboardView.vue`

Peamine orkestreerimiskomponent, mis haldab kogu rakenduse olekut ja koordineerib alamkomponente. Paigutus on 2-veeruline grid:

| Vasak paneel (380 px, sticky) | Parem paneel (1fr, keritav) |
|-------------------------------|------------------------------|
| DatasetSelector               | ResultsPanel                 |
| ModelSelector                 |                              |
| Nupud (Run / Reset)          |                              |

**Olekumuutujad** (`ref()`):
- `selectedDataset` – valitud andmestiku ID
- `selectedModel` – valitud mudeli ID (ml / llm)
- `loading` – pipeline töötlemisolek
- `result` – pipeline tulem-objekt
- `elapsedMs` – pipeline täitmisaeg
- `error` – veatekst

**Meetodid**:
- `handleRun()` – käivitab pipeline API kaudu
- `handleReset()` – tühjendab valikud ja tulemused
- `canRun()` – valideerib, kas Run-nupp on lubatud

---

## 2. Andmestiku valik – DatasetSelector

**Fail**: `src/components/DatasetSelector.vue`

- Kuvab 7 andmestikku (D1–D7) grid-kaartidena
- `v-model` sidumine valitud ID-ga
- Iga kaart näitab: ID, kirjete arv, nimi, kirjeldus
- Andmed tulevad: `getDatasets()` → `src/services/api.js`

---

## 3. Mudeli valik – ModelSelector

**Fail**: `src/components/ModelSelector.vue`

- 2 valikut 2-veerulises grid-is:
  - **ml** – Machine Learning CSV projektsioon (C-02)
  - **llm** – Large Language Model JSON kontekst (C-03)
- Iga kaart kuvab väljundi tüübi badge, nime, kirjelduse
- `v-model` sidumine valitud mudeli ID-ga
- Andmed tulevad: `getModels()` → `src/services/api.js`

---

## 4. Tulemuste kuvamine – ResultsPanel

**Fail**: `src/components/ResultsPanel.vue`

Kuvab pipeline täitmise tulemused:

1. **Laadimisolek** – spinner + "Pipeline running…"
2. **Tühi olek** – juhendtekst
3. **Tulemuste päis** – tulemus-badge (Success / Partial Success / Failed), andmestik & mudel, aeg
4. **Arvude grid** (6 mõõdikut): accounts_total, transactions_total, transactions_emitted_sv, transactions_dropped, ml_rows, llm_contexts
5. **Pipeline etappide logi** – READ_INPUT → STANDARDIZE_TO_SV → VALIDATE_SCHEMA → CHECK_INVARIANTS → PROJECT_ML → PROJECT_LLM → WRITE_OUTPUTS
6. **Probleemide nimekiri** – raskusaste (ERROR/WARN), kood, teade, esinemisarv
7. **ML projektsiooni eelvaade** – HTML tabel (dünaamiliste veergudega), esimesed 5 rida
8. **LLM konteksti eelvaade** – narratiiv-tekst, konto kokkuvõtte statistika, tipptarbekategooriad ribadega

---

## 5. API teenus

**Fail**: `src/services/api.js`

| Funktsioon | Kirjeldus |
|---|---|
| `getDatasets()` | Tagastab 7 andmestikku (ID, nimi, kirjete arv) |
| `getModels()` | Tagastab 2 mudelit: ML (CSV), LLM (JSON) |
| `runPipeline(datasetId, modelId)` | POST `/api/run` → pipeline tulemus |

Backend: `http://localhost:5000`, Vite proxy: `/api` → backend.

---

## 6. Olemasolevate teekide kontroll

### vue-i18n

**Ei kasutata.** Projekt kasutab kohandatud composable'it:

| Fail | Kirjeldus |
|---|---|
| `src/composables/useI18n.js` | Tõlkemootor (punkt-notatsioon, parameetrite interpoleerimine) |
| `src/i18n/en.json` | Inglise tõlked |
| `src/i18n/et.json` | Eesti tõlked |

Keelevahetaja (ET/EN nupp) asub `App.vue` päises.

### Pinia / Vuex / muu state management

**Ei kasutata.** Kogu olekuhaldus toimub:
- Kohalike `ref()` muutujatega DashboardView's
- Vanema-lapse suhtlus `props` ja `emit` kaudu
- `v-model` kahepoolseks sidumiseks
- Composable'id jagatud loogika jaoks (`useI18n`)

```
DashboardView (konteiner)
  ├─ selectedDataset: ref
  ├─ selectedModel: ref
  ├─ result: ref
  ├─ loading: ref
  └─ error: ref
        │
        ├──→ DatasetSelector  (emit: update:modelValue)
        ├──→ ModelSelector     (emit: update:modelValue)
        └──→ ResultsPanel      (props: result, elapsedMs, loading)
```

### Modal / Dialog komponent

**Ei ole olemas.** Tulemused, vead ja andmed kuvatakse inline-sektsioonidena. Olemasolevad UI elemendid:
- Kaardid (`.card`)
- Badge'id (`.badge`, `.badge-success`, `.badge-error`, `.badge-warning`, `.badge-info`)
- Nupud (`.btn`, `.btn-primary`, `.btn-accent`, `.btn-outline`)
- Grid-paigutused
- Põhiline veakuvamise kast (inline DashboardView's)

---

## 7. Failide koondnimekiri

| # | Fail | Otstarve |
|---|------|----------|
| 1 | `src/App.vue` | Juurkomponent (päis + keelevahetaja) |
| 2 | `src/main.js` | Sisenemispunkt |
| 3 | `src/views/DashboardView.vue` | Pealeht (orkestreeija) |
| 4 | `src/components/DatasetSelector.vue` | Andmestiku valik |
| 5 | `src/components/ModelSelector.vue` | Mudeli valik |
| 6 | `src/components/ResultsPanel.vue` | Tulemuste kuvamine (ML CSV + LLM JSON) |
| 7 | `src/router/index.js` | Ruuteri seadistus |
| 8 | `src/services/api.js` | API klient |
| 9 | `src/composables/useI18n.js` | i18n composable |
| 10 | `src/i18n/en.json` | Inglise tõlked |
| 11 | `src/i18n/et.json` | Eesti tõlked |
| 12 | `src/assets/base.css` | Disainisüsteem (CSS muutujad) |
| 13 | `src/assets/main.css` | Globaalsed utiliidid |
| 14 | `package.json` | Sõltuvused |
| 15 | `vite.config.js` | Ehitusseadistus |

---

## 8. Kokkuvõte

| Aspekt | Olek |
|--------|------|
| Raamistik | Vue 3 (Composition API) |
| State management | Puudub (Vue ref) |
| Ruuter | vue-router (üks Dashboard marsruut) |
| i18n | Kohandatud composable (EN/ET) – **mitte** vue-i18n |
| Modal / Dialog | **Puudub** – tuleb luua |
| Peavaade | DashboardView.vue |
| Valiku komponendid | DatasetSelector, ModelSelector |
| Tulemuste komponent | ResultsPanel (projektsioonid: ML CSV + LLM JSON) |
| Paketihaldur | npm |
| Ehitustööriist | Vite 7.1.11 |
| Testimine | Vitest |
| Stiilimine | CSS kohandatud muutujatega |
