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
    <p>{{ t('results.empty') }}</p>
  </div>

  <!-- Results -->
  <div v-else class="results">
    <!-- Header row -->
    <div class="results-header card">
      <div class="rh-top">
        <span class="badge" :class="outcomeBadge">{{ outcomeLabel }}</span>
        <span class="rh-time" :title="t('results.elapsed')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" /><polyline points="12,6 12,12 16,14" />
          </svg>
          {{ elapsedFormatted }}
        </span>
      </div>
      <div class="rh-bottom">
        <span class="rh-dataset">{{ result.datasetName }}</span>
        <span class="rh-sep">&rarr;</span>
        <span class="rh-model">ML + LLM</span>
      </div>
    </div>

    <!-- Counts -->
    <div class="counts-grid">
      <div class="count-item card">
        <span class="count-value">{{ result.counts.accounts_total }}</span>
        <span class="count-label">{{ t('results.counts.accounts') }}</span>
      </div>
      <div class="count-item card">
        <span class="count-value">{{ result.counts.transactions_total }}</span>
        <span class="count-label">{{ t('results.counts.transactions') }}</span>
      </div>
      <div class="count-item card">
        <span class="count-value">{{ result.counts.transactions_emitted_sv }}</span>
        <span class="count-label">{{ t('results.counts.emitted') }}</span>
      </div>
      <div class="count-item card">
        <span class="count-value" :class="{ 'text-warn': result.counts.transactions_dropped > 0 }">
          {{ result.counts.transactions_dropped }}
        </span>
        <span class="count-label">{{ t('results.counts.dropped') }}</span>
      </div>
      <div class="count-item card">
        <span class="count-value">{{ result.counts.ml_rows }}</span>
        <span class="count-label">{{ t('results.counts.mlRows') }}</span>
      </div>
      <div class="count-item card">
        <span class="count-value">{{ result.counts.llm_contexts }}</span>
        <span class="count-label">{{ t('results.counts.llmContexts') }}</span>
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

/* ── Results header ── */
.results-header {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 1.15rem 1.35rem;
  margin-bottom: 0.75rem;
}

.rh-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rh-bottom {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.rh-dataset {
  font-weight: 700;
  font-size: 1.05rem;
  font-family: 'Fira Code', monospace;
  color: var(--color-heading);
}

.rh-sep {
  color: var(--vt-c-text-light-2);
  font-size: 1.1rem;
}

.rh-model {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--brand-primary);
}

.rh-time {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--brand-accent-dark);
}

/* ── Counts grid ── */
.counts-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

@media (max-width: 600px) {
  .counts-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.count-item {
  padding: 0.7rem 0.85rem;
  text-align: center;
}

.count-value {
  display: block;
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--brand-primary);
  line-height: 1.2;
}

.count-value.text-warn {
  color: var(--brand-warning);
}

.count-label {
  font-size: 0.75rem;
  color: var(--vt-c-text-light-2);
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

.subsection-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0.8rem 0 0.45rem;
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
