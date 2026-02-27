<script setup>
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const MODEL_CATALOG = [
  { id: 'anthropic_claude35_sonnet', label: 'Anthropic Claude 3.5 Sonnet' },
  { id: 'openai_gpt4o', label: 'OpenAI GPT-4o' },
  { id: 'google_gemini15_pro', label: 'Google Gemini 1.5 Pro' },
]

defineProps({
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const defaultModel = MODEL_CATALOG[0]
</script>

<template>
  <div class="selector-group unavailable-block">
    <div class="unavailable-header">
      <h3 class="selector-title">
        <span class="selector-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </span>
        {{ t('models.forwardingTitle') }}
      </h3>
      <span class="status-badge">{{ t('models.notAvailable') }}</span>
    </div>

    <!-- Default selected model (read-only) -->
    <div class="chips-area">
      <span class="chip chip-selected">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <polyline points="20 6 9 17 4 12" />
        </svg>
        {{ defaultModel.label }}
      </span>
    </div>

    <p class="default-hint">{{ t('models.defaultSelectedHint', { model: defaultModel.label }) }}</p>

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
</template>

<style scoped>
.selector-group {
  margin-bottom: 1.5rem;
}

.unavailable-block {
  background: var(--color-background-mute);
  border: 1.5px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: 1rem 1.1rem;
  opacity: 0.7;
  cursor: not-allowed;
}

.unavailable-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.65rem;
}

.selector-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--color-heading);
  margin: 0;
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

.default-hint {
  font-size: 0.75rem;
  color: var(--vt-c-text-light-2);
  margin-bottom: 0.5rem;
}

.other-models {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
</style>
