<script setup>
import { computed } from 'vue'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const props = defineProps({
  result: { type: Object, default: null },
  elapsedMs: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
})

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
      <div class="rh-left">
        <span class="badge" :class="outcomeBadge">{{ outcomeLabel }}</span>
        <span class="rh-dataset">{{ result.datasetName }}</span>
        <span class="rh-sep">&rarr;</span>
        <span class="rh-model">{{ result.modelId === 'ml' ? 'ML' : 'LLM' }}</span>
      </div>
      <div class="rh-right">
        <span class="rh-time" :title="t('results.elapsed')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" /><polyline points="12,6 12,12 16,14" />
          </svg>
          {{ elapsedFormatted }}
        </span>
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
        <div v-for="stage in result.stageLog" :key="stage.stage" class="stage-row">
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

    <!-- ML Preview -->
    <div v-if="result.mlPreview" class="section card">
      <h4 class="section-title">{{ t('results.mlPreview.title') }} ({{ result.mlPreview.totalRows }} {{ t('results.mlPreview.totalRows') }})</h4>
      <div class="table-wrap">
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
      <p class="preview-note">{{ t('results.mlPreview.showingFirst', { total: result.mlPreview.totalRows }) }}</p>
    </div>

    <!-- LLM Preview -->
    <div v-if="result.llmPreview" class="section card">
      <h4 class="section-title">{{ t('results.llmPreview.title') }}</h4>

      <div class="llm-narrative">
        <p>{{ result.llmPreview.narrative }}</p>
      </div>

      <div class="llm-stats">
        <div class="llm-stat">
          <span class="llm-stat-label">{{ t('results.llmPreview.period') }}</span>
          <span class="llm-stat-value">{{ result.llmPreview.accountSummary.periodStart }} – {{ result.llmPreview.accountSummary.periodEnd }}</span>
        </div>
        <div class="llm-stat">
          <span class="llm-stat-label">{{ t('results.llmPreview.income') }}</span>
          <span class="llm-stat-value income">+{{ result.llmPreview.accountSummary.totalIncome.toFixed(2) }} EUR</span>
        </div>
        <div class="llm-stat">
          <span class="llm-stat-label">{{ t('results.llmPreview.expenses') }}</span>
          <span class="llm-stat-value expense">{{ result.llmPreview.accountSummary.totalExpenses.toFixed(2) }} EUR</span>
        </div>
        <div class="llm-stat">
          <span class="llm-stat-label">{{ t('results.llmPreview.netFlow') }}</span>
          <span class="llm-stat-value" :class="result.llmPreview.accountSummary.netFlow >= 0 ? 'income' : 'expense'">
            {{ result.llmPreview.accountSummary.netFlow >= 0 ? '+' : '' }}{{ result.llmPreview.accountSummary.netFlow.toFixed(2) }} EUR
          </span>
        </div>
      </div>

      <h5 class="subsection-title">{{ t('results.llmPreview.categories') }}</h5>
      <div class="categories-list">
        <div v-for="cat in result.llmPreview.topCategories" :key="cat.category" class="cat-row">
          <span class="cat-name">{{ cat.category }}</span>
          <span class="cat-bar-wrap">
            <span
              class="cat-bar"
              :style="{
                width: Math.min(100, Math.abs(cat.total) / 30) + '%',
                background: cat.total >= 0 ? 'var(--brand-success)' : 'var(--brand-primary)',
              }"
            ></span>
          </span>
          <span class="cat-total" :class="cat.total >= 0 ? 'income' : ''">
            {{ cat.total >= 0 ? '+' : '' }}{{ cat.total.toFixed(2) }}
          </span>
          <span class="cat-count">{{ cat.count }}x</span>
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
  justify-content: space-between;
  align-items: center;
  padding: 0.85rem 1.1rem;
  margin-bottom: 0.75rem;
}

.rh-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.rh-dataset {
  font-weight: 600;
  font-size: 0.88rem;
  font-family: 'Fira Code', monospace;
}

.rh-sep {
  color: var(--vt-c-text-light-2);
}

.rh-model {
  font-weight: 700;
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

/* ── ML table ── */
.table-wrap {
  overflow-x: auto;
  margin: 0 -0.5rem;
  padding: 0 0.5rem;
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

/* ── LLM preview ── */
.llm-narrative {
  background: var(--color-background-soft);
  border-left: 3px solid var(--brand-accent);
  padding: 0.75rem 1rem;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 0.88rem;
  line-height: 1.55;
  margin-bottom: 0.75rem;
}

.llm-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

@media (max-width: 500px) {
  .llm-stats {
    grid-template-columns: 1fr;
  }
}

.llm-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  background: var(--color-background-soft);
  border-radius: var(--radius-sm);
}

.llm-stat-label {
  font-size: 0.78rem;
  color: var(--vt-c-text-light-2);
}

.llm-stat-value {
  font-weight: 600;
  font-size: 0.88rem;
  font-family: 'Fira Code', monospace;
}

.llm-stat-value.income {
  color: var(--brand-success);
}

.llm-stat-value.expense {
  color: var(--brand-error);
}

/* ── Categories ── */
.categories-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.cat-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.84rem;
  padding: 0.25rem 0;
}

.cat-name {
  min-width: 80px;
  font-weight: 500;
}

.cat-bar-wrap {
  flex: 1;
  height: 8px;
  background: var(--color-background-mute);
  border-radius: 4px;
  overflow: hidden;
}

.cat-bar {
  display: block;
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.cat-total {
  min-width: 80px;
  text-align: right;
  font-family: 'Fira Code', monospace;
  font-size: 0.82rem;
  font-weight: 600;
}

.cat-total.income {
  color: var(--brand-success);
}

.cat-count {
  min-width: 30px;
  text-align: right;
  font-size: 0.75rem;
  color: var(--vt-c-text-light-2);
}
</style>
