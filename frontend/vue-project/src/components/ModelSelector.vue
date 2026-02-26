<script setup>
import { computed, ref } from 'vue'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const MODEL_CATALOG = [
  { id: 'openai_gpt4o', label: 'OpenAI GPT-4o' },
  { id: 'anthropic_claude35_sonnet', label: 'Anthropic Claude 3.5 Sonnet' },
  { id: 'google_gemini15_pro', label: 'Google Gemini 1.5 Pro' },
]

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const dropdownOpen = ref(false)

const availableModels = computed(() =>
  MODEL_CATALOG.filter((m) => !props.modelValue.includes(m.id)),
)

function addModel(id) {
  emit('update:modelValue', [...props.modelValue, id])
  dropdownOpen.value = false
}

function removeModel(id) {
  if (props.disabled) return
  const next = props.modelValue.filter((m) => m !== id)
  emit('update:modelValue', next)
}

function getLabel(id) {
  return MODEL_CATALOG.find((m) => m.id === id)?.label ?? id
}

function toggleDropdown() {
  if (!props.disabled && availableModels.value.length > 0) {
    dropdownOpen.value = !dropdownOpen.value
  }
}
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
      {{ t('models.forwardTo') }}
    </h3>

    <!-- Selected model chips -->
    <div class="chips-area">
      <span
        v-for="id in modelValue"
        :key="id"
        class="chip"
        :class="{ disabled }"
      >
        {{ getLabel(id) }}
        <button
          v-if="!disabled"
          class="chip-remove"
          :aria-label="t('models.removeModel')"
          @click="removeModel(id)"
        >&times;</button>
      </span>

      <span v-if="modelValue.length === 0" class="no-selection-hint">
        {{ t('models.noneSelectedHint') }}
      </span>
    </div>

    <!-- Add model dropdown -->
    <div v-if="availableModels.length > 0" class="dropdown-wrap">
      <button
        class="btn btn-outline add-model-btn"
        :disabled="disabled"
        @click="toggleDropdown"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        {{ t('models.addModel') }}
      </button>

      <ul v-if="dropdownOpen" class="dropdown-list">
        <li
          v-for="m in availableModels"
          :key="m.id"
          class="dropdown-item"
          @click="addModel(m.id)"
        >
          {{ m.label }}
        </li>
      </ul>
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
  margin-bottom: 0.5rem;
}

.selector-icon {
  display: flex;
  color: var(--brand-accent);
}

.chips-area {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  min-height: 2rem;
  margin-bottom: 0.6rem;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.65rem;
  background: rgba(0, 49, 84, 0.08);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--color-heading);
}

.chip.disabled {
  opacity: 0.55;
}

.chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  margin: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--vt-c-text-light-2);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chip-remove:hover {
  background: rgba(231, 76, 60, 0.12);
  color: var(--brand-error);
}

.no-selection-hint {
  font-size: 0.82rem;
  color: var(--vt-c-text-light-2);
  padding: 0.3rem 0;
}

.dropdown-wrap {
  position: relative;
}

.add-model-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  padding: 0.35rem 0.75rem;
}

.dropdown-list {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 240px;
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  list-style: none;
  padding: 0.25rem 0;
  margin: 0;
  z-index: 10;
}

.dropdown-item {
  padding: 0.5rem 0.85rem;
  font-size: 0.85rem;
  color: var(--color-heading);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.dropdown-item:hover {
  background: rgba(0, 49, 84, 0.06);
}
</style>
