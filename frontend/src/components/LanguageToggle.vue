<script setup>
import { computed } from 'vue'
import { useI18n } from '@/composables/useI18n'

const { locale, setLocale } = useI18n()

const isEnglish = computed(() => locale.value === 'en')

function toggle() {
  setLocale(isEnglish.value ? 'et' : 'en')
}

function handleClick(lang) {
  setLocale(lang)
}
</script>

<template>
  <div
    class="lang-switch"
    role="switch"
    :aria-checked="isEnglish"
    aria-label="Language toggle: ET / EN"
    tabindex="0"
    @click="toggle"
    @keydown.enter.prevent="toggle"
    @keydown.space.prevent="toggle"
  >
    <span
      class="lang-switch-label"
      :class="{ active: !isEnglish }"
      @click.stop="handleClick('et')"
    >ET</span>
    <span class="lang-switch-track">
      <span class="lang-switch-thumb" :class="{ right: isEnglish }" />
    </span>
    <span
      class="lang-switch-label"
      :class="{ active: isEnglish }"
      @click.stop="handleClick('en')"
    >EN</span>
  </div>
</template>

<style scoped>
.lang-switch {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
  user-select: none;
  outline: none;
  border-radius: var(--radius-sm);
  padding: 0.15rem 0.1rem;
}

.lang-switch:focus-visible {
  outline: 2px solid var(--brand-accent);
  outline-offset: 2px;
}

.lang-switch-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--vt-c-text-light-2);
  transition: color var(--transition-fast);
  cursor: pointer;
  line-height: 1;
}

.lang-switch-label.active {
  color: var(--brand-primary);
}

.lang-switch-track {
  position: relative;
  width: 28px;
  height: 16px;
  background: var(--color-background-mute);
  border: 1.5px solid var(--color-border-hover);
  border-radius: 999px;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.lang-switch:hover .lang-switch-track {
  border-color: var(--brand-accent);
}

.lang-switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--brand-accent);
  transition: transform var(--transition-fast);
}

.lang-switch-thumb.right {
  transform: translateX(12px);
}
</style>
