<script setup>
import { getModels } from '@/services/api'

const models = getModels()

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
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      </span>
      Mudel
    </h3>
    <p class="selector-hint">Vali v\u00e4ljundi t\u00fc\u00fcp: ML tabeliprojectsioon v\u00f5i LLM kontekst</p>

    <div class="model-grid">
      <button
        v-for="m in models"
        :key="m.id"
        class="model-card card"
        :class="{ active: modelValue === m.id, disabled }"
        :disabled="disabled"
        @click="select(m.id)"
      >
        <div class="model-header">
          <span class="model-icon-wrap">
            <svg v-if="m.icon === 'chart'" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" />
            </svg>
            <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a8 8 0 0 1 8 8c0 3-1.5 5.5-4 7v3H8v-3c-2.5-1.5-4-4-4-7a8 8 0 0 1 8-8z" />
              <path d="M10 22h4" />
            </svg>
          </span>
          <span class="model-output-type badge badge-info">{{ m.outputType }}</span>
        </div>
        <div class="model-name">{{ m.name }}</div>
        <div class="model-desc">{{ m.description }}</div>
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

.model-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

@media (max-width: 600px) {
  .model-grid {
    grid-template-columns: 1fr;
  }
}

.model-card {
  padding: 1rem 1.1rem;
  text-align: left;
  cursor: pointer;
  border: 1.5px solid var(--color-border);
  background: var(--color-background);
  transition: all var(--transition-fast);
}

.model-card:hover:not(.disabled) {
  border-color: var(--brand-primary);
}

.model-card.active {
  border-color: var(--brand-primary);
  background: rgba(0, 49, 84, 0.04);
  box-shadow: 0 0 0 2px rgba(0, 49, 84, 0.15);
}

.model-card.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.model-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-sm);
  background: rgba(0, 49, 84, 0.06);
  color: var(--brand-primary);
}

.model-name {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--color-heading);
  margin-bottom: 0.25rem;
}

.model-desc {
  font-size: 0.8rem;
  color: var(--vt-c-text-light-2);
  line-height: 1.45;
}
</style>
