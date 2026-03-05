<script setup>
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const MODEL_CATALOG = [
  { id: 'llm_llama_local', label: 'Meta Llama 3.1 8B Instruct' },
  { id: 'llm_mistral_local', label: 'Mistral 7B Instruct v0.3' },
  { id: 'llm_qwen_local', label: 'Qwen2.5 7B Instruct' },
  { id: 'ml_xgboost_local', label: 'XGBoost (treenitud kohalikul andmestikul)' },
  { id: 'ml_catboost_local', label: 'CatBoost (treenitud kohalikul andmestikul)' },
]

defineProps({
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const defaultModel = MODEL_CATALOG[0]
</script>

<template>
  <div class="selector-group">
    <h3 class="selector-title">
      <span class="selector-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      </span>
      {{ t('models.forwardingTitle') }}
      <span class="status-badge">{{ t('models.notAvailable') }}</span>
    </h3>
    <p class="selector-hint">{{ t('model.hint') }}</p>

    <div class="unavailable-block">
      <!-- Default selected model (read-only) -->
      <div class="chips-area">
        <span class="chip chip-selected">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          {{ defaultModel.label }}
        </span>
      </div>

      <!-- Other models listed as disabled -->
      <div class="other-models">
        <span
          v-for="m in MODEL_CATALOG.slice(1)"
          :key="m.id"
          class="chip chip-disabled"
        >
          {{ m.label }}
        </span>
      </div>
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

.status-badge {
  font-size: 0.62rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  background: var(--color-border-hover);
  color: var(--vt-c-text-light-2);
  white-space: nowrap;
  margin-left: auto;
}

.selector-hint {
  font-size: 0.82rem;
  color: var(--vt-c-text-light-2);
  margin-bottom: 0.75rem;
}

.unavailable-block {
  background: var(--color-background-mute);
  border: 1.5px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: 0.85rem 1rem;
  opacity: 0.7;
  cursor: not-allowed;
  transition: border-color var(--transition-fast);
}

.unavailable-block:hover {
  border-color: var(--brand-accent);
}

.chips-area {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.45rem;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.65rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--color-heading);
}

.chip-selected {
  background: rgba(0, 137, 122, 0.1);
  border-color: var(--brand-accent);
  color: var(--brand-accent-dark);
}

.chip-selected svg {
  color: var(--brand-accent);
}

.chip-disabled {
  background: rgba(0, 49, 84, 0.05);
  opacity: 0.5;
}

.other-models {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
</style>
