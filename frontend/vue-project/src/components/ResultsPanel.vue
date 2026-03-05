<script setup>
import { computed } from 'vue'
import { useI18n } from '@/composables/useI18n'
import RunResultDetails from './RunResultDetails.vue'

const { t } = useI18n()

const props = defineProps({
  batchResult: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  runProgress: { type: Object, default: () => ({ done: 0, total: 0 }) },
})

const emit = defineEmits(['open-dataset-detail', 'open-projection'])

const isSingleMode = computed(() => props.batchResult?.selectedDatasetIds.length === 1)

const singleDatasetResult = computed(() => {
  if (!isSingleMode.value || !props.batchResult) return null
  const id = props.batchResult.selectedDatasetIds[0]
  return props.batchResult.datasetResults[id] ?? null
})

const overallBadge = computed(() => {
  if (!props.batchResult) return ''
  const map = {
    SUCCESS: 'badge-success',
    PARTIAL_SUCCESS: 'badge-warning',
    FAIL: 'badge-error',
    RUNNING: 'badge-info',
  }
  return map[props.batchResult.overallStatus] || 'badge-info'
})

const overallLabel = computed(() => {
  if (!props.batchResult) return ''
  const s = props.batchResult.overallStatus
  if (s === 'RUNNING') return t('results.runningShort')
  return t('results.outcome.' + s)
})

function datasetStatusBadge(dr) {
  if (!dr) return 'badge-info'
  const map = {
    SUCCESS: 'badge-success',
    PARTIAL_SUCCESS: 'badge-warning',
    FAIL: 'badge-error',
    ERROR: 'badge-error',
    RUNNING: 'badge-info',
  }
  return map[dr.status] || 'badge-info'
}

function formatMs(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(2)} s`
}
</script>

<template>
  <h3 class="results-section-title">
    <span class="results-section-icon">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14,2 14,8 20,8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    </span>
    {{ t('results.summaryTitle') }}
  </h3>
  <p class="results-section-hint">{{ t('results.empty') }}</p>

  <!-- Loading (no results yet) -->
  <div v-if="loading && !batchResult" class="loading-panel card">
    <div class="spinner"></div>
    <p>{{ t('results.loading') }}</p>
  </div>

  <!-- Empty state -->
  <div v-else-if="!batchResult" class="empty-panel card">
    <div class="empty-icon">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14,2 14,8 20,8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    </div>
  </div>

  <!-- Single dataset: inline detail (no modal) -->
  <template v-else-if="isSingleMode">
    <div v-if="singleDatasetResult?.status === 'RUNNING'" class="loading-panel card">
      <div class="spinner"></div>
      <p>{{ t('results.loading') }}</p>
    </div>
    <RunResultDetails
      v-else-if="singleDatasetResult"
      :dataset-result="singleDatasetResult"
      @open-projection="emit('open-projection', $event)"
    />
  </template>

  <!-- Multi-dataset: batch overview + cards -->
  <template v-else>
    <!-- Overview card -->
    <div class="batch-overview card">
      <div class="batch-overview-top">
        <div class="batch-status-row">
          <span class="overview-label">{{ t('results.batch.overall') }}</span>
          <span class="badge" :class="overallBadge">{{ overallLabel }}</span>
        </div>
        <span v-if="loading" class="progress-text">
          {{ t('results.progress', { done: runProgress.done, total: runProgress.total }) }}
        </span>
      </div>
      <div class="batch-datasets-row">
        <span class="overview-label">{{ t('results.batch.title') }}:</span>
        <div class="batch-chips">
          <span v-for="id in batchResult.selectedDatasetIds" :key="id" class="dataset-chip">
            {{ id }}
          </span>
        </div>
      </div>
    </div>

    <!-- Dataset result cards grid -->
    <div class="dataset-results-grid">
      <button
        v-for="id in batchResult.selectedDatasetIds"
        :key="id"
        class="dataset-result-card card"
        :disabled="batchResult.datasetResults[id]?.status === 'RUNNING'"
        @click="emit('open-dataset-detail', { datasetId: id })"
      >
        <div class="drc-header">
          <span class="drc-id">{{ id }}</span>
          <span class="badge badge-sm" :class="datasetStatusBadge(batchResult.datasetResults[id])">
            {{ batchResult.datasetResults[id]?.status === 'RUNNING'
              ? t('results.runningShort')
              : (batchResult.datasetResults[id]?.status || '…') }}
          </span>
        </div>

        <!-- Running state -->
        <div v-if="batchResult.datasetResults[id]?.status === 'RUNNING'" class="drc-running">
          <div class="mini-spinner"></div>
        </div>

        <!-- Done state -->
        <template v-else>
          <div class="drc-duration">{{ formatMs(batchResult.datasetResults[id]?.durationMs) }}</div>
          <div v-if="batchResult.datasetResults[id]?.result" class="drc-counts">
            <span>{{ t('results.counts.accounts') }}: {{ batchResult.datasetResults[id].result.counts.accounts_total }}</span>
            <span>Tx: {{ batchResult.datasetResults[id].result.counts.transactions_total }}</span>
          </div>
          <div v-if="batchResult.datasetResults[id]?.error" class="drc-error">
            {{ batchResult.datasetResults[id].error }}
          </div>
          <div class="drc-action">{{ t('results.batch.openDetail') }} →</div>
        </template>
      </button>
    </div>
  </template>
</template>

<style scoped>
/* Section header */
.results-section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--color-heading);
  margin-bottom: 0.25rem;
}

.results-section-icon {
  display: flex;
  color: var(--brand-accent);
}

.results-section-hint {
  font-size: 0.82rem;
  color: var(--vt-c-text-light-2);
  margin-bottom: 0.75rem;
}

/* Loading */
.loading-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem;
  text-align: center;
  color: var(--vt-c-text-light-2);
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--color-border);
  border-top-color: var(--brand-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Empty */
.empty-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 2rem;
  text-align: center;
  color: var(--vt-c-text-light-2);
}

.empty-icon {
  opacity: 0.35;
}

/* Batch overview card */
.batch-overview {
  padding: 1rem 1.1rem;
  margin-bottom: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.batch-overview-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.batch-status-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.overview-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--vt-c-text-light-2);
}

.progress-text {
  font-size: 0.78rem;
  color: var(--brand-accent-dark);
  font-weight: 600;
}

.batch-datasets-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.batch-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.dataset-chip {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  font-family: 'Fira Code', monospace;
  color: var(--brand-primary);
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.15rem 0.45rem;
}

/* Dataset result cards grid */
.dataset-results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.6rem;
}

.dataset-result-card {
  padding: 0.8rem;
  text-align: left;
  cursor: pointer;
  border: 1.5px solid var(--color-border);
  background: var(--color-background);
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-height: 100px;
}

.dataset-result-card:not(:disabled):hover {
  border-color: var(--brand-accent);
  box-shadow: var(--shadow-card-hover);
}

.dataset-result-card:disabled {
  cursor: default;
  opacity: 0.8;
}

.drc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.3rem;
}

.drc-id {
  font-weight: 700;
  font-size: 1rem;
  color: var(--brand-primary);
  font-family: 'Fira Code', monospace;
}

.badge-sm {
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
}

.drc-running {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 0.5rem 0;
}

.mini-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border);
  border-top-color: var(--brand-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.drc-duration {
  font-size: 0.75rem;
  font-family: 'Fira Code', monospace;
  color: var(--brand-accent-dark);
  font-weight: 600;
}

.drc-counts {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  font-size: 0.72rem;
  color: var(--vt-c-text-light-2);
}

.drc-error {
  font-size: 0.72rem;
  color: var(--brand-error);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drc-action {
  margin-top: auto;
  font-size: 0.72rem;
  color: var(--brand-accent);
  font-weight: 600;
}
</style>
