<script setup>
import { computed } from 'vue'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const props = defineProps({
  result: { type: Object, default: null },
  elapsedMs: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['open-projection'])

const outcomeBadge = computed(() => {
  if (!props.result) return ''
  const map = { SUCCESS: 'badge-success', PARTIAL_SUCCESS: 'badge-warning', FAIL: 'badge-error' }
  return map[props.result.outcome] || 'badge-info'
})

const outcomeLabel = computed(() => {
  if (!props.result) return ''
  return t('results.outcome.' + props.result.outcome)
})

const elapsedFormatted = computed(() => {
  if (props.elapsedMs == null) return '—'
  if (props.elapsedMs < 1000) return `${props.elapsedMs} ms`
  return `${(props.elapsedMs / 1000).toFixed(2)} s`
})

function fmt(val) {
  return val != null ? val : '—'
}

function stageBadge(stage) {
  if (stage.errors > 0) return 'badge-error'
  if (stage.warnings > 0) return 'badge-warning'
  return 'badge-success'
}

function stageLabel(stage) {
  return t('results.stages.' + stage.stage)
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

  <!-- Loading state -->
  <div v-if="loading" class="loading-panel card">
    <div class="spinner"></div>
    <p>{{ t('results.loading') }}</p>
  </div>

  <!-- Empty state -->
  <div v-else-if="!result" class="empty-panel card">
    <div class="empty-icon">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14,2 14,8 20,8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    </div>
  </div>

  <!-- Results -->
  <div v-else class="results">
    <!-- ═══ Summary card ═══ -->
    <div class="summary-card card">
      <!-- Top: status + dataset + elapsed -->
      <div class="summary-top">
        <div class="summary-main">
          <div class="summary-status-row">
            <span class="badge" :class="outcomeBadge">{{ outcomeLabel }}</span>
          </div>
          <div class="summary-dataset">
            <span class="summary-label">{{ t('results.dataset') }}</span>
            <span class="summary-value">{{ result.datasetName }}</span>
          </div>
          <div class="summary-elapsed">
            <span class="summary-label">{{ t('results.elapsed') }}</span>
            <span class="summary-value summary-time">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" /><polyline points="12,6 12,12 16,14" />
              </svg>
              {{ elapsedFormatted }}
            </span>
          </div>
        </div>
      </div>

      <!-- Bottom: meta counts in smaller text -->
      <div class="summary-meta">
        <div class="meta-item">
          <span class="meta-value">{{ fmt(result.counts.accounts_total) }}</span>
          <span class="meta-label">{{ t('results.counts.accounts') }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-value">{{ fmt(result.counts.transactions_total) }}</span>
          <span class="meta-label">{{ t('results.counts.transactions') }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-value">{{ fmt(result.counts.transactions_emitted_sv) }}</span>
          <span class="meta-label">{{ t('results.counts.emitted') }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-value" :class="{ 'text-warn': result.counts.transactions_dropped > 0 }">
            {{ fmt(result.counts.transactions_dropped) }}
          </span>
          <span class="meta-label">{{ t('results.counts.dropped') }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-value">{{ fmt(result.counts.ml_rows) }}</span>
          <span class="meta-label">{{ t('results.counts.mlRows') }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-value">{{ fmt(result.counts.llm_contexts) }}</span>
          <span class="meta-label">{{ t('results.counts.llmContexts') }}</span>
        </div>
      </div>
    </div>

    <!-- Stage log -->
    <div class="section card">
      <h4 class="section-title">{{ t('results.stages.title') }}</h4>
      <div class="stage-list">
        <div v-for="(stage, idx) in result.stageLog" :key="stage.stage" class="stage-row">
          <span class="stage-num">{{ idx + 1 }}</span>
          <span class="stage-name">{{ stageLabel(stage) }}</span>
          <span class="stage-counts">
            <span v-if="stage.errors > 0" class="badge badge-error">{{ stage.errors }} {{ t('results.stages.errors') }}</span>
            <span v-if="stage.warnings > 0" class="badge badge-warning">{{ stage.warnings }} {{ t('results.stages.warnings') }}</span>
          </span>
          <span class="badge" :class="stageBadge(stage)">
            {{ stage.errors > 0 ? 'ERROR' : stage.warnings > 0 ? 'WARN' : 'OK' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Issues -->
    <div v-if="result.issues.length > 0" class="section card">
      <h4 class="section-title">{{ t('results.issues.title') }} ({{ result.issues.length }})</h4>
      <div class="issues-list">
        <div v-for="(issue, i) in result.issues" :key="i" class="issue-row">
          <span class="badge" :class="issue.severity === 'ERROR' ? 'badge-error' : 'badge-warning'">
            {{ issue.severity }}
          </span>
          <span class="issue-code">{{ issue.code }}</span>
          <span class="issue-msg">{{ issue.message }}</span>
          <span v-if="issue.count" class="issue-count">&times;{{ issue.count }}</span>
        </div>
      </div>
    </div>

    <!-- Projection summaries -->
    <div v-if="result.mlPreview || result.llmPreview" class="section card">
      <h4 class="section-title">{{ t('flow.projections') }}</h4>
      <div class="projection-summaries">
        <div v-if="result.mlPreview" class="projection-row">
          <span class="projection-label">{{ t('results.mlPreview.summary', { count: result.mlPreview.totalRows }) }}</span>
          <button class="btn btn-outline btn-sm" @click="emit('open-projection', { kind: 'ml' })">
            {{ t('actions.view') }}
          </button>
        </div>
        <div v-if="result.llmPreview" class="projection-row">
          <span class="projection-label">{{ t('results.llmPreview.summary', { count: result.counts.transactions_total }) }}</span>
          <button class="btn btn-outline btn-sm" @click="emit('open-projection', { kind: 'llm' })">
            {{ t('actions.view') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Results section header ── */
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

/* ── Loading ── */
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

/* ── Empty ── */
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

/* ═══ Summary card ═══ */
.summary-card {
  padding: 0;
  margin-bottom: 0.75rem;
  overflow: hidden;
}

.summary-top {
  padding: 1.25rem 1.35rem;
}

.summary-main {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.summary-status-row {
  margin-bottom: 0.15rem;
}

.summary-status-row .badge {
  font-size: 0.88rem;
  padding: 0.2rem 0.75rem;
}

.summary-dataset,
.summary-elapsed {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.summary-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--vt-c-text-light-2);
  min-width: 5.5rem;
}

.summary-value {
  font-size: 1.05rem;
  font-weight: 700;
  font-family: 'Fira Code', monospace;
  color: var(--color-heading);
}

.summary-time {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--brand-accent-dark);
  font-size: 0.95rem;
}

/* ── Meta counts ── */
.summary-meta {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--color-border);
  background: var(--color-background-soft);
}

.meta-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.65rem 0.5rem;
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.meta-item:nth-child(3n) {
  border-right: none;
}

.meta-item:nth-last-child(-n+3) {
  border-bottom: none;
}

.meta-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--brand-primary);
  line-height: 1.2;
}

.meta-value.text-warn {
  color: var(--brand-warning);
}

.meta-label {
  font-size: 0.68rem;
  color: var(--vt-c-text-light-2);
  text-align: center;
}

@media (max-width: 600px) {
  .summary-meta {
    grid-template-columns: repeat(2, 1fr);
  }
  .meta-item:nth-child(3n) {
    border-right: 1px solid var(--color-border);
  }
  .meta-item:nth-child(2n) {
    border-right: none;
  }
  .meta-item:nth-last-child(-n+3) {
    border-bottom: 1px solid var(--color-border);
  }
  .meta-item:nth-last-child(-n+2) {
    border-bottom: none;
  }
}

/* ── Section cards ── */
.section {
  padding: 1rem 1.1rem;
  margin-bottom: 0.75rem;
}

.section-title {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--color-heading);
  margin-bottom: 0.65rem;
}

/* ── Stage log ── */
.stage-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.stage-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--color-border);
}

.stage-row:last-child {
  border-bottom: none;
}

.stage-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 50%;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
  background: var(--color-background-mute);
  color: var(--vt-c-text-light-2);
}

.stage-name {
  flex: 1;
  font-size: 0.84rem;
}

.stage-counts {
  display: flex;
  gap: 0.3rem;
}

/* ── Issues ── */
.issues-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.issue-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0;
  font-size: 0.84rem;
  border-bottom: 1px solid var(--color-border);
}

.issue-row:last-child {
  border-bottom: none;
}

.issue-code {
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  font-size: 0.8rem;
  color: var(--brand-primary);
  min-width: 50px;
}

.issue-msg {
  flex: 1;
  color: var(--vt-c-text-light-2);
}

.issue-count {
  font-weight: 600;
  font-size: 0.82rem;
  color: var(--vt-c-text-light-2);
}

/* ── Projection summaries ── */
.projection-summaries {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.projection-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.45rem 0;
  border-bottom: 1px solid var(--color-border);
}

.projection-row:last-child {
  border-bottom: none;
}

.projection-label {
  font-size: 0.88rem;
  font-family: 'Fira Code', monospace;
  color: var(--color-heading);
}

.btn-sm {
  padding: 0.25rem 0.65rem;
  font-size: 0.78rem;
}
</style>
