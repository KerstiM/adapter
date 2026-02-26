<script setup>
import { ref, computed } from 'vue'
import DatasetSelector from '@/components/DatasetSelector.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import ResultsPanel from '@/components/ResultsPanel.vue'
import FlowStepper from '@/components/FlowStepper.vue'
import { runPipeline } from '@/services/api'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const selectedDataset = ref('')
const selectedModels = ref([])
const loading = ref(false)
const result = ref(null)
const elapsedMs = ref(0)
const error = ref('')

const MODEL_LABELS = {
  openai_gpt4o: 'OpenAI GPT-4o',
  anthropic_claude35_sonnet: 'Claude 3.5 Sonnet',
  google_gemini15_pro: 'Gemini 1.5 Pro',
}

const activeStep = computed(() => {
  if (!selectedDataset.value) return 1
  if (selectedModels.value.length === 0) return 2
  if (!result.value) return 3
  return 4
})

const canRun = () => selectedDataset.value && selectedModels.value.length > 0 && !loading.value

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
  selectedModels.value = []
  result.value = null
  elapsedMs.value = 0
  error.value = ''
}

function modelLabel(id) {
  return MODEL_LABELS[id] || id
}
</script>

<template>
  <div class="dashboard-wrap">
    <FlowStepper :active-step="activeStep" />

    <div class="dashboard">
      <!-- Left column: Data selection + Model selection -->
      <aside class="config-panel">
        <DatasetSelector v-model="selectedDataset" :disabled="loading" />

        <!-- Forward-to summary row -->
        <div class="forward-row">
          <span class="forward-label">{{ t('models.forwardTo') }}:</span>
          <span v-if="selectedModels.length === 0" class="forward-hint">
            {{ t('models.noneSelectedHint') }}
          </span>
          <span v-else class="forward-chips">
            <span v-for="id in selectedModels" :key="id" class="forward-chip">
              {{ modelLabel(id) }}
            </span>
          </span>
        </div>

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
        <ResultsPanel :result="result" :elapsed-ms="elapsedMs" :loading="loading" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: grid;
  grid-template-columns: 380px 1fr;
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

/* ── Forward-to summary row ── */
.forward-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  margin-bottom: 1rem;
  background: var(--color-background-soft);
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
}

.forward-label {
  font-weight: 600;
  color: var(--color-heading);
  white-space: nowrap;
}

.forward-hint {
  color: var(--vt-c-text-light-2);
  font-style: italic;
  font-size: 0.82rem;
}

.forward-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.forward-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.55rem;
  background: rgba(0, 49, 84, 0.08);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--color-heading);
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
