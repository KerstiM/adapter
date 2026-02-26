<script setup>
import { getDatasets } from '@/services/api'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
const datasets = getDatasets()

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

function select(id) {
  if (!props.disabled) {
    emit('update:modelValue', id)
  }
}
</script>

<template>
  <div class="selector-group">
    <h3 class="selector-title">
      <span class="selector-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
        </svg>
      </span>
      {{ t('dataset.title') }}
    </h3>
    <p class="selector-hint">{{ t('dataset.hint') }}</p>

    <div class="dataset-grid">
      <button
        v-for="ds in datasets"
        :key="ds.id"
        class="dataset-card card"
        :class="{ active: modelValue === ds.id, disabled }"
        :disabled="disabled"
        @click="select(ds.id)"
      >
        <div class="ds-header">
          <span class="ds-id">{{ ds.id }}</span>
          <span class="ds-records">{{ ds.records }} {{ t('dataset.recordsUnit') }}</span>
        </div>
        <div class="ds-name">{{ ds.name }}</div>
        <div class="ds-desc">{{ t('dataset.' + ds.id) }}</div>
      </button>

      <!-- Custom data card (not yet available) -->
      <button
        class="dataset-card card custom-card custom-unavailable"
        disabled
      >
        <div class="ds-header">
          <span class="ds-id custom-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </span>
          <span class="custom-status-badge">{{ t('data.notAvailable') }}</span>
        </div>
        <div class="ds-name custom-title">{{ t('data.chooseYourData') }}</div>
        <div class="ds-desc">
          <strong>{{ t('data.allowedFormatsTitle') }}</strong>
        </div>
        <div class="ds-formats">{{ t('data.allowedFormatsBody') }}</div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.selector-group {
  margin-bottom: 1.5rem;
}

.selector-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--color-heading);
  margin-bottom: 0.25rem;
}

.selector-icon {
  display: flex;
  color: var(--brand-accent);
}

.selector-hint {
  font-size: 0.82rem;
  color: var(--vt-c-text-light-2);
  margin-bottom: 0.75rem;
}

.dataset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.6rem;
}

.dataset-card {
  padding: 0.75rem 0.9rem;
  text-align: left;
  cursor: pointer;
  border: 1.5px solid var(--color-border);
  background: var(--color-background);
  transition: all var(--transition-fast);
}

.dataset-card:hover:not(.disabled) {
  border-color: var(--brand-accent);
}

.dataset-card.active {
  border-color: var(--brand-accent);
  background: rgba(0, 180, 160, 0.06);
  box-shadow: 0 0 0 2px rgba(0, 180, 160, 0.18);
}

.dataset-card.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ds-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.3rem;
}

.ds-id {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--brand-primary);
}

.ds-records {
  font-size: 0.72rem;
  color: var(--vt-c-text-light-2);
}

.ds-name {
  font-size: 0.78rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  color: var(--vt-c-text-light-2);
  margin-bottom: 0.2rem;
  word-break: break-all;
}

.ds-desc {
  font-size: 0.8rem;
  color: var(--color-text);
}

.custom-card {
  border-style: dashed;
}

.custom-unavailable {
  background: var(--color-background-mute);
  opacity: 0.6;
  cursor: not-allowed;
  position: relative;
}

.custom-unavailable:hover {
  border-color: var(--color-border);
}

.custom-status-badge {
  font-size: 0.62rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  background: var(--color-border-hover);
  color: var(--vt-c-text-light-2);
  white-space: nowrap;
}

.custom-icon {
  display: flex;
  align-items: center;
  color: var(--brand-accent);
}

.custom-title {
  font-family: inherit;
  font-weight: 600;
  color: var(--color-heading);
}

.ds-formats {
  font-size: 0.72rem;
  color: var(--vt-c-text-light-2);
  margin-top: 0.25rem;
  line-height: 1.4;
}
</style>
