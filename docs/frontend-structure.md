# Frontend vaate kaardistus (Frontend Structure Map)

## Ülevaade

- **Raamistik**: Vue 3 (Composition API, `<script setup>`)
- **Ehitustööriist**: Vite 7.1.11
- **Ruuter**: vue-router 4.6.3 (kaks marsruuti: `/` → Dashboard, `/docs` → DocsView)
- **Juurkaust**: `frontend/`

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

- Kuvab 10 andmestikku (D1–D10) grid-kaartidena
- `v-model` sidumine valitud ID-ga
- Iga kaart näitab: ID, kirjete arv, nimi, kirjeldus
- Andmed tulevad: `getDatasets()` → `src/services/api.js`

---

## 3. Sihtmudelite valik – ModelSelector

**Fail**: `src/components/ModelSelector.vue`

- Sihtmudelite valik: 4 LLM (Llama 3.1, Mistral 7B, Qwen 2.5, Gemma 2) ja 2 ML (XGBoost, CatBoost)
- Mudelite valik on **valikuline** – pipeline käivitub ka ilma mudeliteta
- Chip-põhine UI: valitud mudelid kuvatakse chip'idena, saab lisada/eemaldada
- `v-model` sidumine valitud mudelite massiiviga
- Pipeline toodab alati baas-projektsioonid (ML CSV + LLM JSON) sõltumata mudelivalikust; mudeli valik lisab mudeli-spetsiifilised väljundid

---

## 4. Tulemuste kuvamine – ResultsPanel

**Fail**: `src/components/ResultsPanel.vue`

Kuvab pipeline täitmise tulemused:

1. **Laadimisolek** – spinner + "Pipeline running…"
2. **Tühi olek** – juhendtekst
3. **Tulemuste päis** – tulemus-badge (Success / Partial Success / Failed), andmestik & mudel, aeg
4. **Arvude grid** (6 mõõdikut): accounts_total, transactions_total, transactions_emitted_sv, transactions_dropped, ml_rows, llm_contexts
5. **Pipeline etappide logi** – READ_INPUT → STANDARDIZE_TO_SV → VALIDATE_SCHEMA → CHECK_INVARIANTS → PROJECT_ML → PROJECT_LLM → FORMAT_FOR_MODEL → WRITE_OUTPUTS
6. **Probleemide nimekiri** – raskusaste (ERROR/WARN), kood, teade, esinemisarv
7. **ML projektsiooni eelvaade** – HTML tabel (dünaamiliste veergudega), esimesed 5 rida
8. **LLM konteksti eelvaade** – narratiiv-tekst, konto kokkuvõtte statistika, tipptarbekategooriad ribadega

---

## 5. Keelevahetaja – LanguageToggle

**Fail**: `src/components/LanguageToggle.vue`

- Kompaktne ET/EN keelevahetaja nupp
- Kasutab `useI18n` composable'i `locale` ja `setLocale` meetodit
- Kuvab kaks keelenuppu, aktiivne keel on esiletõstetud

---

## 6. Tulemuste detailvaade – RunResultDetails

**Fail**: `src/components/RunResultDetails.vue`

- Ühe dataseti pipeline'i tulemuse detailne kuvamine
- Props: `datasetResult` (objekt: `{ datasetId, status, durationMs, result, error }`)
- Emits: `open-projection` (projektsioonide modaali avamine)
- Kuvab: outcome badge, mõõdikud, etappide logi, probleemid, ML/LLM eelvaated
- Kasutab `useI18n` tõlgete jaoks

---

## 7. Projektsiooni modaal – ProjectionModal

**Fail**: `src/components/ProjectionModal.vue`

- Üldotstarbeline modaal-dialoog projektsioonide detailvaateks
- Teleport-põhine (renderdab `<body>` alla), ESC-klahviga sulguv
- ML projektsioon: HTML tabel (dünaamilised veerud, esimesed 5 rida)
- LLM projektsioon: JSON-dump monospace formaadis
- DashboardView edastab sisu `<slot>` kaudu

---

## 8. Dokumentatsioonivaade – DocsView

**Fail**: `src/views/DocsView.vue`

- Marsruut: `/docs`
- Kuvab projekti dokumentatsiooni markdown-formaadis (kasutab `useMarkdown` renderdajat)
- Sidebar-navigatsioon: tuumdokumendid ja dataseti-dokumendid (andmed: `src/data/docs.js`)
- Tõlked `useI18n` kaudu

---

## 9. API teenus

**Fail**: `src/services/api.js`

Kogu andmevahetus backend'iga — null mock-andmeid.

| Funktsioon | Kirjeldus |
|---|---|
| `getDatasets()` | Tagastab 10 andmestikku (D1–D10): ID, nimi, kirjete arv |
| `getModels()` | Tagastab 6 mudelit: 3 LLM (Llama 3.1, Mistral 7B, Qwen 2.5) + 2 ML (XGBoost, CatBoost) |
| `runPipeline(datasetId, selectedModelIds)` | POST `/api/run` → pipeline tulemus. `selectedModelIds` on massiiv mudeli-ID-dest. |

Backend: `python -m entrypoints.api` (stdlib http.server, port 5000). Vite proxy: `/api` → backend.

---

## 10. Olemasolevate teekide kontroll

### vue-i18n

**Ei kasutata.** Projekt kasutab kohandatud composable'it:

| Fail | Kirjeldus |
|---|---|
| `src/composables/useI18n.js` | Tõlkemootor (punkt-notatsioon, parameetrite interpoleerimine) |
| `src/composables/useMarkdown.js` | Minimaalne markdown → HTML renderdaja (pealkirjad, koodiplokid, tabelid, loendid, lingid). Kasutatakse DocsView's. |
| `src/i18n/en.json` | Inglise tõlked |
| `src/i18n/et.json` | Eesti tõlked |

Keelevahetaja on eraldiseisev komponent `LanguageToggle.vue` (vt sektsioon 5).

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
        ├──→ DatasetSelector     (emit: update:modelValue)
        ├──→ ModelSelector       (emit: update:modelValue)
        ├──→ ResultsPanel        (props: result, elapsedMs, loading; emit: open-projection)
        │     └──→ RunResultDetails  (props: datasetResult; emit: open-projection)
        └──→ ProjectionModal     (props: open, title; emit: close)
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

## 11. Failide koondnimekiri

| # | Fail | Otstarve |
|---|------|----------|
| 1 | `src/App.vue` | Juurkomponent (päis + LanguageToggle) |
| 2 | `src/main.js` | Sisenemispunkt |
| 3 | `src/views/DashboardView.vue` | Pealeht (orkestreeija) |
| 4 | `src/views/DocsView.vue` | Dokumentatsioonivaade (markdown-renderdaja) |
| 5 | `src/components/DatasetSelector.vue` | Andmestiku valik (D1–D10) |
| 6 | `src/components/ModelSelector.vue` | Sihtmudelite valik (4 LLM + 2 ML, valikuline) |
| 7 | `src/components/ResultsPanel.vue` | Tulemuste kuvamine (ML CSV + LLM JSON) |
| 8 | `src/components/RunResultDetails.vue` | Ühe dataseti tulemuse detailvaade |
| 9 | `src/components/LanguageToggle.vue` | ET/EN keelevahetaja |
| 10 | `src/components/ProjectionModal.vue` | Projektsiooni modaal-dialoog |
| 11 | `src/router/index.js` | Ruuteri seadistus (2 marsruuti) |
| 12 | `src/services/api.js` | API klient (backend-ühendus) |
| 13 | `src/composables/useI18n.js` | i18n composable (kohandatud tõlkemootor) |
| 14 | `src/composables/useMarkdown.js` | Markdown → HTML renderdaja |
| 15 | `src/utils/downloadFile.js` | Faili allalaadimine brauseris (CSV/JSON/TXT) |
| 16 | `src/data/docs.js` | Dokumentatsiooni sisu (DocsView andmed) |
| 17 | `src/i18n/en.json` | Inglise tõlked |
| 18 | `src/i18n/et.json` | Eesti tõlked |
| 19 | `src/assets/base.css` | Disainisüsteem (CSS muutujad) |
| 20 | `src/assets/main.css` | Globaalsed utiliidid |
| 21 | `package.json` | Sõltuvused |
| 22 | `vite.config.js` | Ehitusseadistus |

---

## 12. Kokkuvõte

| Aspekt | Olek |
|--------|------|
| Raamistik | Vue 3 (Composition API) |
| State management | Puudub (Vue ref) |
| Ruuter | vue-router (kaks marsruuti: Dashboard + Docs) |
| i18n | Kohandatud composable (EN/ET) – **mitte** vue-i18n |
| Modal / Dialog | **Olemas** – ProjectionModal.vue (Teleport-põhine) |
| Peavaade | DashboardView.vue |
| Dokumentatsioonivaade | DocsView.vue (markdown-renderdaja) |
| Keelevahetaja | LanguageToggle.vue (ET/EN) |
| Valiku komponendid | DatasetSelector (D1–D10), ModelSelector (4 LLM + 2 ML, valikuline) |
| Tulemuste komponendid | ResultsPanel + RunResultDetails |
| Projektsiooni modaal | ProjectionModal.vue (ML tabel + LLM JSON) |
| Utiliidid | useMarkdown.js (renderdaja), downloadFile.js (faili allalaadimine) |
| Paketihaldur | npm |
| Ehitustööriist | Vite 7.1.11 |
| Testimine | Vitest |
| Stiilimine | CSS kohandatud muutujatega |
