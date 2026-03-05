<script setup>
import { ref, computed } from 'vue'
import DatasetSelector from '@/components/DatasetSelector.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import ResultsPanel from '@/components/ResultsPanel.vue'
import ProjectionModal from '@/components/ProjectionModal.vue'
import { runPipeline } from '@/services/api'
import { useI18n } from '@/composables/useI18n'
import { downloadFile, MIME, sanitise } from '@/utils/downloadFile'

const { t } = useI18n()

const selectedDataset = ref('')
const selectedModels = ref(['anthropic_claude35_sonnet'])
const loading = ref(false)
const result = ref(null)
const elapsedMs = ref(0)
const error = ref('')

const canRun = () => selectedDataset.value && !loading.value

async function handleRun() {
  if (!canRun()) return

  loading.value = true
  result.value = null
  error.value = ''
  elapsedMs.value = 0

  try {
    const response = await runPipeline(selectedDataset.value, selectedModels.value)
    result.value = response.result
    elapsedMs.value = response.elapsed_ms
  } catch (e) {
    error.value = e.message || t('errors.runFailed')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  selectedDataset.value = ''
  selectedModels.value = ['anthropic_claude35_sonnet']
  result.value = null
  elapsedMs.value = 0
  error.value = ''
}

const activeProjectionKind = ref(null)

function handleOpenProjection({ kind }) {
  activeProjectionKind.value = kind
}

function handleCloseProjection() {
  activeProjectionKind.value = null
}

const projectionModalTitle = computed(() => {
  if (activeProjectionKind.value === 'ml') return t('results.mlPreview.title')
  if (activeProjectionKind.value === 'llm') return t('results.llmPreview.title')
  return ''
})

const llmContextJson = computed(() => {
  if (!result.value?.llmPreview) return ''
  const raw = result.value.llmPreview.rawContexts
  if (raw) return JSON.stringify(raw, null, 2)
  return JSON.stringify(result.value.llmPreview, null, 2)
})

const downloadFormat = ref('default')

const hasProjectionData = computed(() => {
  if (activeProjectionKind.value === 'ml') {
    return !!(result.value?.mlPreview?.rows?.length)
  }
  if (activeProjectionKind.value === 'llm') {
    return !!(result.value?.llmPreview)
  }
  return false
})

function buildMlCsv() {
  if (!result.value?.mlPreview) return ''
  const { headers, rows } = result.value.mlPreview
  return [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
}

function buildFilename(kind, ext) {
  const dataset = sanitise(selectedDataset.value || result.value?.datasetName)
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const base = dataset || ts
  const suffix = dataset ? `_${ts}` : ''
  return `${kind}_projection_${base}${suffix}.${ext}`
}

function handleDownload() {
  const kind = activeProjectionKind.value
  if (!kind || !hasProjectionData.value) return

  const fmt =
      downloadFormat.value === 'default'
          ? (kind === 'ml'
              ? 'csv'
              : 'json')
          : downloadFormat.value

  const content = kind === 'ml'
      ? buildMlCsv()
      : llmContextJson.value

  if (!content) return

  const mime = MIME[fmt] ?? MIME.txt
  const filename = buildFilename(kind, fmt)
  downloadFile(content, filename, mime)
}

const copyFeedback = ref('')

async function handleCopy() {
  let text = ''
  if (activeProjectionKind.value === 'ml' && result.value?.mlPreview) {
    const { headers, rows } = result.value.mlPreview
    text = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  } else if (activeProjectionKind.value === 'llm') {
    text = llmContextJson.value
  }
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copyFeedback.value = t('projectionModal.copied')
    setTimeout(() => { copyFeedback.value = '' }, 2000)
  } catch {
    /* clipboard not available */
  }
}
</script>

<template>
  <div class="dashboard-wrap">
    <div class="dashboard">
      <!-- Left column: Data selection + Model selection -->
      <aside class="config-panel">
        <DatasetSelector v-model="selectedDataset" :disabled="loading" />

        <ModelSelector v-model="selectedModels" :disabled="loading" />

        <div class="actions">
          <button
            class="btn btn-accent run-btn"
            :disabled="!canRun()"
            @click="handleRun"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5,3 19,12 5,21" />
            </svg>
            {{ t('actions.run') }}
          </button>
          <button
            class="btn btn-outline"
            :disabled="loading"
            @click="handleReset"
          >
            {{ t('actions.reset') }}
          </button>
        </div>

        <div v-if="error" class="error-box">
          {{ error }}
        </div>
      </aside>

      <!-- Right column: Results + Projections -->
      <main class="results-panel">
        <ResultsPanel
          :result="result"
          :elapsed-ms="elapsedMs"
          :loading="loading"
          @open-projection="handleOpenProjection"
        />
      </main>
    </div>

    <!-- Projection modal -->
    <ProjectionModal
      :open="activeProjectionKind !== null"
      :title="projectionModalTitle"
      @close="handleCloseProjection"
    >
      <!-- ML: full table -->
      <template v-if="activeProjectionKind === 'ml'">
        <template v-if="result?.mlPreview && result.mlPreview.rows.length > 0">
          <div class="modal-table-wrap">
            <table class="preview-table">
              <thead>
                <tr>
                  <th v-for="h in result.mlPreview.headers" :key="h">{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in result.mlPreview.rows" :key="i">
                  <td v-for="(cell, j) in row" :key="j">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="preview-note">{{ t('results.mlPreview.allRows', { count: result.mlPreview.totalRows }) }}</p>
        </template>
        <p v-else class="no-data-msg">{{ t('results.mlPreview.noData') }}</p>
      </template>

      <!-- LLM: full JSON -->
      <template v-if="activeProjectionKind === 'llm'">
        <template v-if="result?.llmPreview">
          <pre class="llm-json">{{ llmContextJson }}</pre>
        </template>
        <p v-else class="no-data-msg">{{ t('results.llmPreview.noData') }}</p>
      </template>

      <!-- Footer: download + copy -->
      <template #footer>
        <span v-if="copyFeedback" class="copy-feedback">{{ copyFeedback }}</span>

        <div class="download-group">
          <select v-model="downloadFormat" class="download-format-select">
            <template v-if="activeProjectionKind === 'ml'">
              <option value="default">CSV</option>
              <option value="txt">TXT</option>
            </template>
            <template v-if="activeProjectionKind === 'llm'">
              <option value="default">JSON</option>
              <option value="txt">TXT</option>
            </template>
          </select>
          <button
            class="btn btn-outline btn-sm"
            :disabled="!hasProjectionData"
            :title="!hasProjectionData ? t('errors.noProjectionData') : t('actions.download')"
            @click="handleDownload"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {{ t('actions.download') }}
          </button>
        </div>

        <button class="btn btn-outline btn-sm" @click="handleCopy">
          {{ t('projectionModal.copy') }}
        </button>
      </template>
    </ProjectionModal>
  </div>
</template>

<style scoped>
.dashboard {
  display: grid;
  grid-template-columns: 540px 1fr;
  gap: 1.5rem;
  align-items: start;
  min-height: calc(100vh - 120px);
}

@media (max-width: 900px) {
  .dashboard {
    grid-template-columns: 1fr;
  }
}

.config-panel {
  position: sticky;
  top: 1rem;
}

.actions {
  display: flex;
  gap: 0.6rem;
  margin-top: 0.25rem;
}

.run-btn {
  flex: 1;
}

.error-box {
  margin-top: 0.75rem;
  padding: 0.65rem 0.85rem;
  background: rgba(231, 76, 60, 0.08);
  border: 1px solid rgba(231, 76, 60, 0.2);
  border-radius: var(--radius-sm);
  color: var(--brand-error);
  font-size: 0.85rem;
}

.results-panel {
  min-width: 0;
}
</style>

<style>
/* Unscoped – modal content lives inside Teleport (outside scoped DOM) */
.modal-table-wrap {
  overflow-x: auto;
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.preview-table th {
  text-align: left;
  padding: 0.4rem 0.6rem;
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--vt-c-text-light-2);
  border-bottom: 2px solid var(--color-border);
  white-space: nowrap;
  background: var(--color-background);
  position: sticky;
  top: 0;
  z-index: 1;
}

.preview-table td {
  padding: 0.35rem 0.6rem;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
  font-family: 'Fira Code', monospace;
  font-size: 0.78rem;
}

.preview-table tbody tr:hover {
  background: var(--color-background-soft);
}

.preview-note {
  font-size: 0.75rem;
  color: var(--vt-c-text-light-2);
  margin-top: 0.5rem;
  text-align: right;
}

.llm-json {
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 1rem;
  font-family: 'Fira Code', monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}

.no-data-msg {
  text-align: center;
  color: var(--vt-c-text-light-2);
  padding: 2rem 1rem;
  font-size: 0.9rem;
}

.copy-feedback {
  font-size: 0.78rem;
  color: var(--brand-accent-dark);
  font-weight: 600;
}

.download-group {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.download-format-select {
  padding: 0.22rem 0.4rem;
  font-size: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-background);
  color: var(--color-heading);
  cursor: pointer;
}

.download-group .btn svg {
  vertical-align: -2px;
  margin-right: 0.2rem;
}
</style>
