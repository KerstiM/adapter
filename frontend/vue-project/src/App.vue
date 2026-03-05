<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterView, RouterLink } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import LanguageToggle from '@/components/LanguageToggle.vue'

const { t } = useI18n()

// JS fallback for browsers without scroll-driven animations
const isScrolled = ref(false)
let scrollHandler
onMounted(() => {
  if (CSS.supports('animation-timeline', 'scroll()')) return
  scrollHandler = () => { isScrolled.value = window.scrollY > 0 }
  window.addEventListener('scroll', scrollHandler, { passive: true })
})
onUnmounted(() => {
  if (scrollHandler) window.removeEventListener('scroll', scrollHandler)
})
</script>

<template>
  <header class="app-header" :class="{ 'is-scrolled': isScrolled }">
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

  <div class="app-body">
    <RouterView />
  </div>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--color-background);
  border-bottom: 1px solid transparent;
  box-shadow: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.app-body {
  max-width: 1440px;
  margin: 1.25rem auto 0;
  padding: 0 1.5rem;
}

/* Scrolled state: JS adds .is-scrolled class */
.app-header.is-scrolled {
  border-bottom-color: var(--color-border);
  box-shadow: 0 2px 12px rgba(0, 49, 84, 0.1);
}

/* Scroll-driven animation as progressive enhancement */
@supports (animation-timeline: scroll()) {
  .app-header {
    animation: header-scrolled-shadow linear both;
    animation-timeline: scroll(root);
    animation-range: 0px 4px;
    /* Reset transition since animation handles it */
    transition: none;
  }

  @keyframes header-scrolled-shadow {
    from {
      border-bottom-color: transparent;
      box-shadow: none;
    }
    to {
      border-bottom-color: var(--color-border);
      box-shadow: 0 2px 12px rgba(0, 49, 84, 0.1);
    }
  }
}

.header-inner {
  /* Horizontal padding aligns content with app-body (1.5rem) */
  max-width: 1440px;
  margin: 0 auto;
  padding: 0.75rem 1.5rem;
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
