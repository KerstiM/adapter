<script setup>
import { RouterView } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import LanguageToggle from '@/components/LanguageToggle.vue'

const { t } = useI18n()
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="brand">
        <div class="brand-text">
          <span class="brand-name">Adapter</span>
          <span class="brand-sub">{{ t('header.subtitle') }}</span>
        </div>
      </div>
      <div class="header-right">
        <LanguageToggle />
        <span class="version-tag">{{ t('header.version') }}</span>
      </div>
    </div>
  </header>

  <RouterView />
</template>

<style scoped>
.app-header {
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background);
  margin-bottom: 1.25rem;
}

.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0.75rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-weight: 800;
  font-size: 1.1rem;
  color: var(--brand-primary);
  line-height: 1.2;
  letter-spacing: -0.01em;
}

.brand-sub {
  font-size: 0.72rem;
  color: var(--vt-c-text-light-2);
  line-height: 1.2;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.version-tag {
  font-size: 0.72rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: var(--color-background-mute);
  color: var(--vt-c-text-light-2);
  font-weight: 500;
}
</style>
