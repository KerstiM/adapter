<script setup>
import { ref } from 'vue'
import DatasetSelector from '@/components/DatasetSelector.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import ResultsPanel from '@/components/ResultsPanel.vue'
import { runPipeline } from '@/services/api'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const selectedDataset = ref('')
const selectedModels = ref([])
const loading = ref(false)
const result = ref(null)
const elapsedMs = ref(0)
const error = ref('')

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
</script>

<template>
  <div class="dashboard">
    <!-- Left panel: configuration -->
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

    <!-- Right panel: results -->
    <main class="results-panel">
      <ResultsPanel :result="result" :elapsed-ms="elapsedMs" :loading="loading" />
    </main>
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
