<script setup>
import { ref, computed } from 'vue'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const ALL_MODELS = [
  { id: 'llama3.1-8b-instruct', label: 'Meta Llama 3.1 8B Instruct', cat: 'llm' },
  { id: 'mistral-7b-instruct-v0.3', label: 'Mistral 7B Instruct v0.3', cat: 'llm' },
  { id: 'qwen2.5-7b-instruct', label: 'Qwen2.5 7B Instruct', cat: 'llm' },
  { id: 'xgboost', label: 'XGBoost', cat: 'ml' },
  { id: 'catboost', label: 'CatBoost', cat: 'ml' },
]

const LLM_MODELS = ALL_MODELS.filter(m => m.cat === 'llm')
const ML_MODELS = ALL_MODELS.filter(m => m.cat === 'ml')

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const mode = ref('proto') // 'proto' | 'production'

const hasSelection = computed(() => props.modelValue.length > 0)

function isSelected(id) {
  return props.modelValue.includes(id)
}

function toggle(id) {
  if (props.disabled) return
  const current = [...props.modelValue]
  const idx = current.indexOf(id)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(id)
  }
  emit('update:modelValue', current)
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
      {{ mode === 'proto' ? t('models.forwardingTitle') : t('models.forwardingTitleProduction') }}
      <span class="status-badge" :class="mode === 'proto' && hasSelection ? 'status-badge--active' : ''">
        {{ mode === 'production' ? t('models.notAvailable') : (hasSelection ? t('models.active') : t('models.optional')) }}
      </span>
      <span class="mode-toggle">
        <button
          class="toggle-btn"
          :class="{ 'toggle-btn--active': mode === 'proto' }"
          @click="mode = 'proto'"
        >
          {{ t('models.modeProto') }}
        </button>
        <button
          class="toggle-btn"
          :class="{ 'toggle-btn--active': mode === 'production' }"
          @click="mode = 'production'"
        >
          {{ t('models.modeProduction') }}
        </button>
      </span>
    </h3>
    <p class="selector-hint">
      {{ mode === 'proto'
        ? (hasSelection ? t('models.hintWithModels') : t('models.hintNoModels'))
        : t('models.hintProduction')
      }}
    </p>

    <!-- Proto mode: model-specific projections selection -->
    <div v-if="mode === 'proto'" class="model-block" :class="{ 'model-block--disabled': disabled }">
      <button class="add-model-btn" disabled :title="t('models.addModel')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        {{ t('models.addModel') }}
      </button>
      <!-- LLM models -->
      <div class="model-category">
        <span class="category-label">{{ t('models.llmCategory') }}</span>
        <div class="chips-area">
          <span
            v-for="m in LLM_MODELS"
            :key="m.id"
            class="chip"
            :class="{
              'chip-selected': isSelected(m.id),
              'chip-idle': !isSelected(m.id),
            }"
            role="button"
            tabindex="0"
            @click="toggle(m.id)"
            @keydown.enter="toggle(m.id)"
            @keydown.space.prevent="toggle(m.id)"
          >
            <svg v-if="isSelected(m.id)" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            {{ m.label }}
          </span>
        </div>
      </div>

      <!-- ML models -->
      <div class="model-category">
        <span class="category-label">{{ t('models.mlCategory') }}</span>
        <div class="chips-area">
          <span
            v-for="m in ML_MODELS"
            :key="m.id"
            class="chip"
            :class="{
              'chip-selected': isSelected(m.id),
              'chip-idle': !isSelected(m.id),
            }"
            role="button"
            tabindex="0"
            @click="toggle(m.id)"
            @keydown.enter="toggle(m.id)"
            @keydown.space.prevent="toggle(m.id)"
          >
            <svg v-if="isSelected(m.id)" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            {{ m.label }}
          </span>
        </div>
      </div>
    </div>

    <!-- Production mode: forwarding (not yet available) -->
    <div v-else class="unavailable-block">
      <button class="add-model-btn" disabled :title="t('models.addModel')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        {{ t('models.addModel') }}
      </button>
      <div class="chips-area">
        <span class="chip chip-selected">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          {{ ALL_MODELS[0].label }}
        </span>
      </div>
      <div class="other-models">
        <span
          v-for="m in ALL_MODELS.slice(1)"
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
}

.status-badge--active {
  background: rgba(0, 137, 122, 0.15);
  color: var(--brand-accent-dark);
}

.mode-toggle {
  display: inline-flex;
  margin-left: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.toggle-btn {
  padding: 0.18rem 0.55rem;
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border: none;
  background: transparent;
  color: var(--vt-c-text-light-2);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.toggle-btn:not(:last-child) {
  border-right: 1px solid var(--color-border);
}

.toggle-btn--active {
  background: var(--brand-accent);
  color: #fff;
}

.toggle-btn:hover:not(.toggle-btn--active) {
  background: var(--color-background-soft);
}

.selector-hint {
  font-size: 0.82rem;
  color: var(--vt-c-text-light-2);
  margin-bottom: 0.75rem;
}

.model-block {
  position: relative;
  background: var(--color-background);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 0.85rem 1rem;
  transition: border-color var(--transition-fast);
}

.add-model-btn {
  position: absolute;
  top: 0.6rem;
  right: 0.7rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.22rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--vt-c-text-light-2);
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: not-allowed;
  opacity: 0.45;
}

.model-block:hover {
  border-color: var(--brand-accent);
}

.model-block--disabled {
  opacity: 0.5;
  pointer-events: none;
}

.unavailable-block {
  position: relative;
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

.unavailable-block .chips-area {
  margin-bottom: 0.45rem;
}

.other-models {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.chip-disabled {
  background: rgba(0, 49, 84, 0.05);
  opacity: 0.5;
  cursor: not-allowed;
}

.model-category {
  margin-bottom: 0.55rem;
}

.model-category:last-child {
  margin-bottom: 0;
}

.category-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vt-c-text-light-2);
  margin-bottom: 0.35rem;
}

.chips-area {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
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
  cursor: pointer;
  user-select: none;
  transition: all var(--transition-fast);
}

.chip:hover {
  border-color: var(--brand-accent);
  background: rgba(0, 137, 122, 0.05);
}

.chip:focus-visible {
  outline: 2px solid var(--brand-accent);
  outline-offset: 1px;
}

.chip-selected {
  background: rgba(0, 137, 122, 0.1);
  border-color: var(--brand-accent);
  color: var(--brand-accent-dark);
}

.chip-selected svg {
  color: var(--brand-accent);
}

.chip-idle {
  background: rgba(0, 49, 84, 0.03);
}
</style>
