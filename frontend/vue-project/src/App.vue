<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="brand">
        <svg class="brand-logo" width="32" height="32" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="8" fill="var(--brand-primary)" />
          <path d="M8 10h6a4 4 0 0 1 0 8H8V10z" fill="var(--brand-accent)" />
          <path d="M8 18h7a4 4 0 0 1 0 8H8V18z" fill="#fff" opacity="0.85" />
          <rect x="20" y="10" width="4" height="16" rx="2" fill="var(--brand-accent)" opacity="0.6" />
        </svg>
        <div class="brand-text">
          <span class="brand-name">Adapter</span>
          <span class="brand-sub">Standardiseerimiskiht</span>
        </div>
      </div>
      <span class="version-tag">prototüüp v0.1</span>
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
  gap: 0.65rem;
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

.version-tag {
  font-size: 0.72rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: var(--color-background-mute);
  color: var(--vt-c-text-light-2);
  font-weight: 500;
}
</style>
