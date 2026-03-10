<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import DatasetSelector from '@/components/DatasetSelector.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import ResultsPanel from '@/components/ResultsPanel.vue'
import ProjectionModal from '@/components/ProjectionModal.vue'
import RunResultDetails from '@/components/RunResultDetails.vue'
import { getDatasets, runPipeline } from '@/services/api'
import { useI18n } from '@/composables/useI18n'
import { downloadFile, MIME, sanitise } from '@/utils/downloadFile'

const { t } = useI18n()

const allDatasets = getDatasets()

// ── Footer shadow: show only when content exists below viewport ──
const hasContentBelow = ref(false)
function updateFooterShadow() {
  hasContentBelow.value = window.scrollY + window.innerHeight < document.documentElement.scrollHeight - 1
}
onMounted(() => {
  updateFooterShadow()
  window.addEventListener('scroll', updateFooterShadow, { passive: true })
  window.addEventListener('resize', updateFooterShadow, { passive: true })
})
onUnmounted(() => {
  window.removeEventListener('scroll', updateFooterShadow)
  window.removeEventListener('resize', updateFooterShadow)
})

// ── Selection state ──
const selectedDatasets = ref([])
const selectedModels = ref([])

// ── Run state ──
const loading = ref(false)
const error = ref('')
const batchResult = ref(null)
const runProgress = ref({ done: 0, total: 0 })

const canRun = computed(() => selectedDatasets.value.length > 0 && !loading.value)

// ── Batch run (sequential) ──
async function handleBatchRun() {
  if (!canRun.value) return

  // Sort IDs by numeric suffix for stable order: D1, D2, ..., D10
  const ids = [...selectedDatasets.value].sort((a, b) => {
    const n = (s) => parseInt(s.replace(/\D/g, ''), 10) || 0
    return n(a) - n(b)
  })

  loading.value = true
  error.value = ''
  runProgress.value = { done: 0, total: ids.length }

  // Initialise all as RUNNING so cards appear immediately
  const datasetResults = {}
  for (const id of ids) {
    datasetResults[id] = { datasetId: id, status: 'RUNNING', durationMs: null, result: null, error: null }
  }
  batchResult.value = {
    startedAt: new Date().toISOString(),
    finishedAt: null,
    selectedDatasetIds: ids,
    overallStatus: 'RUNNING',
    datasetResults,
  }

  for (const id of ids) {
    try {
      const t0 = Date.now()
      const response = await runPipeline(id, selectedModels.value)
      batchResult.value.datasetResults[id] = {
        datasetId: id,
        status: response.result.outcome,
        durationMs: Date.now() - t0,
        result: response.result,
        error: null,
      }
    } catch (e) {
      batchResult.value.datasetResults[id] = {
        datasetId: id,
        status: 'FAIL',
        durationMs: null,
        result: null,
        error: e.message || t('errors.runFailed'),
      }
    }
    runProgress.value.done++
  }

  // Compute overall status
  const statuses = ids.map(id => batchResult.value.datasetResults[id].status)
  const hasOk = statuses.some(s => s === 'SUCCESS' || s === 'PARTIAL_SUCCESS')
  const hasFail = statuses.some(s => s === 'FAIL' || s === 'ERROR')
  batchResult.value.overallStatus = hasOk && hasFail ? 'PARTIAL_SUCCESS' : hasOk ? 'SUCCESS' : 'FAIL'
  batchResult.value.finishedAt = new Date().toISOString()

  loading.value = false
}

// "Run all datasets" — select all then run
function handleRunAll() {
  if (loading.value) return
  selectedDatasets.value = allDatasets.map(d => d.id)
  handleBatchRun()
}

function handleReset() {
  selectedDatasets.value = []
  selectedModels.value = []
  batchResult.value = null
  runProgress.value = { done: 0, total: 0 }
  error.value = ''
  activeDetailDatasetId.value = null
  activeProjectionKind.value = null
}

// ── Dataset detail modal ──
const activeDetailDatasetId = ref(null)

const activeDetailResult = computed(() =>
  activeDetailDatasetId.value && batchResult.value
    ? batchResult.value.datasetResults[activeDetailDatasetId.value] ?? null
    : null
)

function handleOpenDatasetDetail({ datasetId }) {
  activeDetailDatasetId.value = datasetId
}

function handleCloseDatasetDetail() {
  activeDetailDatasetId.value = null
  activeProjectionKind.value = null
}

const detailModalTitle = computed(() => {
  if (!activeDetailDatasetId.value) return ''
  const dr = activeDetailResult.value
  const name = dr?.result?.datasetName || activeDetailDatasetId.value
  return `${activeDetailDatasetId.value} — ${name}`
})

// ── Projection modal (opens on top of detail modal) ──
const activeProjectionKind = ref(null)
const activeModelSuffix = ref(null)
const downloadFormat = ref('default')
const copyFeedback = ref('')

function handleOpenProjection({ kind, modelSuffix }) {
  activeProjectionKind.value = kind
  activeModelSuffix.value = modelSuffix || null
}

function handleCloseProjection() {
  activeProjectionKind.value = null
  activeModelSuffix.value = null
}

const projectionModalTitle = computed(() => {
  if (activeProjectionKind.value === 'ml') return t('results.mlPreview.title')
  if (activeProjectionKind.value === 'llm') return t('results.llmPreview.title')
  if (activeProjectionKind.value === 'model-ml') return `${t('results.mlPreview.title')} — ${activeModelSuffix.value}`
  if (activeProjectionKind.value === 'model-llm') return `${t('results.llmPreview.title')} — ${activeModelSuffix.value}`
  return ''
})

const activeModelProjectionContent = computed(() => {
  const r = projectionSourceResult.value
  if (!r?.modelProjections || !activeModelSuffix.value) return null
  const kind = activeProjectionKind.value === 'model-ml' ? 'ml' : 'llm'
  const mp = r.modelProjections.find(p => p.type === kind && p.modelSuffix === activeModelSuffix.value)
  return mp?.content ?? null
})

const projectionSourceResult = computed(() => {
  // Multi-mode: projection opened from within the detail modal
  if (activeDetailDatasetId.value && batchResult.value) {
    return batchResult.value.datasetResults[activeDetailDatasetId.value]?.result ?? null
  }
  // Single-mode: projection opened inline (no detail modal)
  if (batchResult.value?.selectedDatasetIds.length === 1) {
    const id = batchResult.value.selectedDatasetIds[0]
    return batchResult.value.datasetResults[id]?.result ?? null
  }
  return null
})

const llmContextJson = computed(() => {
  const r = projectionSourceResult.value
  if (!r?.llmPreview) return ''
  const raw = r.llmPreview.rawContexts
  return JSON.stringify(raw ?? r.llmPreview, null, 2)
})

const hasProjectionData = computed(() => {
  if (activeProjectionKind.value === 'ml') {
    return !!(projectionSourceResult.value?.mlPreview?.rows?.length)
  }
  if (activeProjectionKind.value === 'llm') {
    return !!(projectionSourceResult.value?.llmPreview)
  }
  if (activeProjectionKind.value === 'model-ml' || activeProjectionKind.value === 'model-llm') {
    return !!activeModelProjectionContent.value
  }
  return false
})

function buildMlCsv() {
  const r = projectionSourceResult.value
  if (!r?.mlPreview) return ''
  const { headers, rows } = r.mlPreview
  return [headers.join(','), ...rows.map(row => row.join(','))].join('\n')
}

function buildFilename(kind, ext) {
  const dataset = sanitise(activeDetailDatasetId.value || projectionSourceResult.value?.datasetName)
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const base = dataset || ts
  const suffix = dataset ? `_${ts}` : ''
  return `${kind}_projection_${base}${suffix}.${ext}`
}

function handleDownload() {
  const kind = activeProjectionKind.value
  if (!kind || !hasProjectionData.value) return
  const isModelSpecific = kind === 'model-ml' || kind === 'model-llm'
  const fmt = downloadFormat.value === 'default' ? (kind === 'ml' ? 'csv' : 'json') : downloadFormat.value
  let content
  if (isModelSpecific) {
    content = JSON.stringify(activeModelProjectionContent.value, null, 2)
  } else {
    content = kind === 'ml' ? buildMlCsv() : llmContextJson.value
  }
  if (!content) return
  const fileKind = isModelSpecific ? `${kind.replace('model-', '')}_${activeModelSuffix.value}` : kind
  downloadFile(content, buildFilename(fileKind, fmt), MIME[fmt] ?? MIME.txt)
}

async function handleCopy() {
  let text = ''
  if (activeProjectionKind.value === 'ml' && projectionSourceResult.value?.mlPreview) {
    const { headers, rows } = projectionSourceResult.value.mlPreview
    text = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  } else if (activeProjectionKind.value === 'llm') {
    text = llmContextJson.value
  } else if ((activeProjectionKind.value === 'model-ml' || activeProjectionKind.value === 'model-llm') && activeModelProjectionContent.value) {
    text = JSON.stringify(activeModelProjectionContent.value, null, 2)
  }
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copyFeedback.value = t('projectionModal.copied')
    setTimeout(() => { copyFeedback.value = '' }, 2000)
  } catch { /* clipboard not available */ }
}
</script>

<template>
  <div class="dashboard-wrap">
    <div class="dashboard">
      <!-- Left column: selection -->
      <aside class="config-panel">
        <DatasetSelector
          v-model="selectedDatasets"
          :disabled="loading"
        />

        <div class="section-gap"></div>

        <ModelSelector v-model="selectedModels" :disabled="loading" />
      </aside>

      <!-- Right column: results -->
      <main class="results-panel">
        <ResultsPanel
          :batch-result="batchResult"
          :loading="loading"
          :run-progress="runProgress"
          @open-dataset-detail="handleOpenDatasetDetail"
          @open-projection="handleOpenProjection"
        />
      </main>
    </div>

    <!-- Fixed action footer -->
    <footer class="actions-footer" :class="{ 'actions-footer--shadow': hasContentBelow }">
      <div class="actions-inner">
        <div v-if="error" class="error-box">{{ error }}</div>
        <div class="actions-buttons">
          <button
            class="btn btn-accent run-btn"
            :disabled="!canRun"
            @click="handleBatchRun"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5,3 19,12 5,21" />
            </svg>
            {{ t('actions.run') }}
          </button>
          <button
            class="btn btn-outline"
            :disabled="loading"
            @click="handleRunAll"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0">
              <polygon points="5,3 19,12 5,21" />
            </svg>
            <span class="btn-two-line"><span>{{ t('actions.runAllLine1') }}</span><span>{{ t('actions.runAllLine2') }}</span></span>
          </button>
          <button
            class="btn btn-outline"
            :disabled="loading"
            @click="handleReset"
          >
            {{ t('actions.reset') }}
          </button>
        </div>
      </div>
    </footer>

    <!-- ── Dataset detail modal (z-index 1100) ── -->
    <ProjectionModal
      :open="activeDetailDatasetId !== null"
      :title="detailModalTitle"
      :z-index="1100"
      @close="handleCloseDatasetDetail"
    >
      <RunResultDetails
        v-if="activeDetailResult"
        :dataset-result="activeDetailResult"
        @open-projection="handleOpenProjection"
      />
    </ProjectionModal>

    <!-- ── Projection modal (z-index 1200, on top of detail) ── -->
    <ProjectionModal
      :open="activeProjectionKind !== null"
      :title="projectionModalTitle"
      :z-index="1200"
      @close="handleCloseProjection"
    >
      <!-- ML: full table (general) -->
      <template v-if="activeProjectionKind === 'ml'">
        <template v-if="projectionSourceResult?.mlPreview && projectionSourceResult.mlPreview.rows.length > 0">
          <div class="modal-table-wrap">
            <table class="preview-table">
              <thead>
                <tr>
                  <th v-for="h in projectionSourceResult.mlPreview.headers" :key="h">{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in projectionSourceResult.mlPreview.rows" :key="i">
                  <td v-for="(cell, j) in row" :key="j">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="preview-note">{{ t('results.mlPreview.allRows', { count: projectionSourceResult.mlPreview.totalRows }) }}</p>
        </template>
        <p v-else class="no-data-msg">{{ t('results.mlPreview.noData') }}</p>
      </template>

      <!-- LLM: full JSON (general) -->
      <template v-if="activeProjectionKind === 'llm'">
        <template v-if="projectionSourceResult?.llmPreview">
          <pre class="llm-json">{{ llmContextJson }}</pre>
        </template>
        <p v-else class="no-data-msg">{{ t('results.llmPreview.noData') }}</p>
      </template>

      <!-- Model-specific ML projection (JSON) -->
      <template v-if="activeProjectionKind === 'model-ml'">
        <template v-if="activeModelProjectionContent">
          <pre class="llm-json">{{ JSON.stringify(activeModelProjectionContent, null, 2) }}</pre>
        </template>
        <p v-else class="no-data-msg">{{ t('results.mlPreview.noData') }}</p>
      </template>

      <!-- Model-specific LLM projection (JSON) -->
      <template v-if="activeProjectionKind === 'model-llm'">
        <template v-if="activeModelProjectionContent">
          <pre class="llm-json">{{ JSON.stringify(activeModelProjectionContent, null, 2) }}</pre>
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
            <template v-if="activeProjectionKind === 'llm' || activeProjectionKind === 'model-ml' || activeProjectionKind === 'model-llm'">
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
.dashboard-wrap {
  padding-bottom: 5rem;
}

.dashboard {
  display: grid;
  grid-template-columns: 540px 1fr;
  gap: 2.5rem;
  align-items: start;
}

@media (max-width: 900px) {
  .dashboard {
    grid-template-columns: 1fr;
  }
}

.config-panel {
  display: flex;
  flex-direction: column;
}

.actions-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 50;
  background: var(--color-background);
  box-shadow: none;
  transition: box-shadow var(--transition-fast);
  padding: 0.6rem 1.5rem 0.75rem;
}

.actions-footer--shadow {
  box-shadow: 0 -4px 12px rgba(0, 49, 84, 0.08);
}

.actions-inner {
  max-width: 1440px;
  margin: 0 auto;
}

.actions-buttons {
  display: flex;
  gap: 0.6rem;
}

.actions-buttons .btn {
  flex: 1;
}

.btn-two-line {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.2;
}

.btn-two-line span {
  font-weight: 600;
}

.btn-two-line span:last-child {
  opacity: 0.75;
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

.section-gap {
  height: 0.75rem;
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

.btn-sm {
  padding: 0.25rem 0.65rem;
  font-size: 0.78rem;
}
</style>
