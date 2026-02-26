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
- `selectedModels` – valitud sihtmudelite ID-d (massiiv, valikuline)
- `loading` – pipeline töötlemisolek
- `result` – pipeline tulem-objekt
- `elapsedMs` – pipeline täitmisaeg
- `error` – veatekst

**Meetodid**:
- `handleRun()` – käivitab pipeline API kaudu
- `handleReset()` – tühjendab valikud ja tulemused
- `canRun()` – valideerib, kas Run-nupp on lubatud (nõuab ainult andmestiku valikut)

---

## 2. Andmestiku valik – DatasetSelector

**Fail**: `src/components/DatasetSelector.vue`

- Kuvab 7 andmestikku (D1–D7) grid-kaartidena
- `v-model` sidumine valitud ID-ga
- Iga kaart näitab: ID, kirjete arv, nimi, kirjeldus
- Andmed tulevad: `getDatasets()` → `src/services/api.js`

---

## 3. Sihtmudelite valik – ModelSelector (mock)

**Fail**: `src/components/ModelSelector.vue`

- Sihtmudelite mock-valik (OpenAI GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro)
- Mudelite valik on **valikuline** – pipeline käivitub ka ilma mudeliteta
- Chip-põhine UI: valitud mudelid kuvatakse chip'idena, saab lisada/eemaldada
- `v-model` sidumine valitud mudelite massiiviga
- Pipeline toodab alati mõlemad projektsioonid (ML + LLM) sõltumata mudelivalikust

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

## 5. Voo samm-indikaator – FlowStepper

**Fail**: `src/components/FlowStepper.vue`

- Horisontaalne samm-indikaator (stepper), mis näitab pipeline töövoo etappe
- 3 sammu: Andmete valik → Tulemused → Projektsioonid
- Aktiivne samm on visuaalselt esiletõstetud, läbitud sammud on märgistatud
- Prop: `activeStep` (number) – DashboardView arvutab automaatselt

---

## 6. Projektsiooni modaal – ProjectionModal

**Fail**: `src/components/ProjectionModal.vue`

- Üldotstarbeline modaal-dialoog projektsioonide detailvaateks
- Teleport-põhine (renderdab `<body>` alla), ESC-klahviga sulguv
- ML projektsioon: HTML tabel (dünaamilised veerud, esimesed 5 rida)
- LLM projektsioon: JSON-dump monospace formaadis
- DashboardView edastab sisu `<slot>` kaudu

---

## 7. API teenus

**Fail**: `src/services/api.js`

| Funktsioon | Kirjeldus |
|---|---|
| `getDatasets()` | Tagastab 7 andmestikku (ID, nimi, kirjete arv) |
| `getModels()` | Tagastab 2 mudelit: ML (CSV), LLM (JSON) |
| `runPipeline(datasetId, modelId)` | POST `/api/run` → pipeline tulemus |

Backend: `http://localhost:5000`, Vite proxy: `/api` → backend.

---

## 8. Olemasolevate teekide kontroll

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
  ├─ selectedModels: ref (massiiv, valikuline)
  ├─ result: ref
  ├─ loading: ref
  ├─ error: ref
  └─ activeProjectionKind: ref (null / 'ml' / 'llm')
        │
        ├──→ FlowStepper       (props: activeStep)
        ├──→ DatasetSelector    (emit: update:modelValue)
        ├──→ ModelSelector      (emit: update:modelValue)
        ├──→ ResultsPanel       (props: result, elapsedMs, loading; emit: open-projection)
        └──→ ProjectionModal    (props: open, title; emit: close)
```

### Modal / Dialog komponent

**Olemas:** `ProjectionModal.vue` – Teleport-põhine modaal projektsioonide eelvaateks. Olemasolevad UI elemendid:
- Kaardid (`.card`)
- Badge'id (`.badge`, `.badge-success`, `.badge-error`, `.badge-warning`, `.badge-info`)
- Nupud (`.btn`, `.btn-primary`, `.btn-accent`, `.btn-outline`)
- Grid-paigutused
- Modaal-dialoog (ProjectionModal)
- Põhiline veakuvamise kast (inline DashboardView's)

---

## 9. Failide koondnimekiri

| # | Fail | Otstarve |
|---|------|----------|
| 1 | `src/App.vue` | Juurkomponent (päis + keelevahetaja) |
| 2 | `src/main.js` | Sisenemispunkt |
| 3 | `src/views/DashboardView.vue` | Pealeht (orkestreeija) |
| 4 | `src/components/DatasetSelector.vue` | Andmestiku valik |
| 5 | `src/components/ModelSelector.vue` | Sihtmudelite mock-valik (valikuline) |
| 6 | `src/components/ResultsPanel.vue` | Tulemuste kuvamine (ML CSV + LLM JSON) |
| 7 | `src/components/FlowStepper.vue` | Voo samm-indikaator (3 sammu) |
| 8 | `src/components/ProjectionModal.vue` | Projektsiooni modaal-dialoog |
| 9 | `src/router/index.js` | Ruuteri seadistus |
| 10 | `src/services/api.js` | API klient |
| 11 | `src/composables/useI18n.js` | i18n composable |
| 12 | `src/i18n/en.json` | Inglise tõlked |
| 13 | `src/i18n/et.json` | Eesti tõlked |
| 14 | `src/assets/base.css` | Disainisüsteem (CSS muutujad) |
| 15 | `src/assets/main.css` | Globaalsed utiliidid |
| 16 | `package.json` | Sõltuvused |
| 17 | `vite.config.js` | Ehitusseadistus |

---

## 10. Kokkuvõte

| Aspekt | Olek |
|--------|------|
| Raamistik | Vue 3 (Composition API) |
| State management | Puudub (Vue ref) |
| Ruuter | vue-router (üks Dashboard marsruut) |
| i18n | Kohandatud composable (EN/ET) – **mitte** vue-i18n |
| Modal / Dialog | **Olemas** – ProjectionModal.vue (Teleport-põhine) |
| Peavaade | DashboardView.vue |
| Voo samm-indikaator | FlowStepper.vue (3 sammu) |
| Valiku komponendid | DatasetSelector, ModelSelector (mock, valikuline) |
| Tulemuste komponent | ResultsPanel (projektsioonid: ML CSV + LLM JSON) |
| Projektsiooni modaal | ProjectionModal.vue (ML tabel + LLM JSON) |
| Paketihaldur | npm |
| Ehitustööriist | Vite 7.1.11 |
| Testimine | Vitest |
| Stiilimine | CSS kohandatud muutujatega |
