<script setup>
import { RouterView, RouterLink } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import LanguageToggle from '@/components/LanguageToggle.vue'

const { t } = useI18n()
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="header-left">
        <RouterLink to="/" class="brand">
          <div class="brand-text">
            <span class="brand-name">Adapter</span>
            <span class="brand-sub">{{ t('header.subtitle') }}</span>
          </div>
        </RouterLink>

        <nav class="app-nav">
          <RouterLink to="/" class="nav-link" active-class="nav-link-active" exact>
            {{ t('nav.dashboard') }}
          </RouterLink>
          <RouterLink to="/docs" class="nav-link" active-class="nav-link-active">
            {{ t('nav.docs') }}
          </RouterLink>
        </nav>
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
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background);
  margin-bottom: 1.25rem;
}

.header-inner {
  /* No max-width — matches #app width (1440px from main.css) */
  padding: 0.75rem 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

/* Brand as link */
.brand {
  display: flex;
  align-items: center;
  text-decoration: none;
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
  transition: color var(--transition-fast);
}

.brand:hover .brand-name {
  color: var(--brand-primary-light);
}

.brand-sub {
  font-size: 0.72rem;
  color: var(--vt-c-text-light-2);
  line-height: 1.2;
}

/* Navigation */
.app-nav {
  display: flex;
  align-items: center;
  gap: 0.15rem;
}

.nav-link {
  padding: 0.3rem 0.7rem;
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--vt-c-text-light-2);
  text-decoration: none;
  transition: all var(--transition-fast);
}

.nav-link:hover {
  background: var(--color-background-soft);
  color: var(--color-heading);
}

.nav-link-active {
  background: var(--color-background-mute);
  color: var(--brand-primary);
  font-weight: 600;
}

/* Right side */
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
