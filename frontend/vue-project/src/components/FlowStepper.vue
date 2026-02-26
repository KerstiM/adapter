<script setup>
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

defineProps({
  activeStep: { type: Number, default: 1 },
})

const steps = [
  { num: 1, key: 'flow.dataSelection' },
  { num: 2, key: 'flow.modelSelection' },
  { num: 3, key: 'flow.results' },
  { num: 4, key: 'flow.projections' },
]
</script>

<template>
  <nav class="stepper" aria-label="Flow steps">
    <ol class="stepper-list">
      <li
        v-for="step in steps"
        :key="step.num"
        class="stepper-item"
        :class="{
          active: step.num === activeStep,
          completed: step.num < activeStep,
        }"
        :aria-current="step.num === activeStep ? 'step' : undefined"
      >
        <span class="step-number">{{ step.num }}</span>
        <span class="step-label">{{ t(step.key) }}</span>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.stepper {
  margin-bottom: 1.5rem;
}

.stepper-list {
  display: flex;
  list-style: none;
  padding: 0;
  gap: 0.25rem;
}

.stepper-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  color: var(--vt-c-text-light-2);
  transition: all var(--transition-fast);
  position: relative;
}

/* connector line between steps */
.stepper-item + .stepper-item::before {
  content: '';
  position: absolute;
  left: -0.5rem;
  top: 50%;
  width: 0.75rem;
  height: 1.5px;
  background: var(--color-border-hover);
  transform: translateY(-50%);
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 50%;
  font-size: 0.78rem;
  font-weight: 700;
  flex-shrink: 0;
  border: 1.5px solid var(--color-border-hover);
  color: var(--vt-c-text-light-2);
  background: var(--color-background);
  transition: all var(--transition-fast);
}

.step-label {
  white-space: nowrap;
  font-weight: 500;
}

/* ── Active step ── */
.stepper-item.active .step-number {
  background: var(--brand-accent);
  border-color: var(--brand-accent);
  color: var(--vt-c-white);
}

.stepper-item.active .step-label {
  color: var(--brand-primary);
  font-weight: 700;
}

/* ── Completed step ── */
.stepper-item.completed .step-number {
  background: var(--brand-accent-light);
  border-color: var(--brand-accent-light);
  color: var(--vt-c-white);
}

.stepper-item.completed .step-label {
  color: var(--brand-accent-dark);
}

.stepper-item.completed + .stepper-item::before {
  background: var(--brand-accent-light);
}
</style>
