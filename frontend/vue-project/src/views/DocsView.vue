<script setup>
import { ref, computed } from 'vue'
import { renderMarkdown } from '@/composables/useMarkdown'
import { CORE_DOCS, DATASET_DOCS } from '@/data/docs'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const selectedId = ref(CORE_DOCS[0].id)

const allDocs = [...CORE_DOCS, ...DATASET_DOCS]

const selectedDoc = computed(() => allDocs.find(d => d.id === selectedId.value) ?? allDocs[0])
const renderedContent = computed(() => renderMarkdown(selectedDoc.value.content))
</script>

<template>
  <div class="docs-layout">
    <!-- Sidebar -->
    <aside class="docs-sidebar">
      <div class="sidebar-group">
        <div class="sidebar-group-title">{{ t('docs.coreTitle') }}</div>
        <button
          v-for="doc in CORE_DOCS"
          :key="doc.id"
          class="sidebar-item"
          :class="{ active: selectedId === doc.id }"
          @click="selectedId = doc.id"
        >
          <span class="sidebar-item-title">{{ t('docs.' + doc.id + '.title') }}</span>
          <span class="sidebar-item-sub">{{ t('docs.' + doc.id + '.subtitle') }}</span>
        </button>
      </div>

      <div class="sidebar-group">
        <div class="sidebar-group-title">{{ t('docs.datasetsTitle') }}</div>
        <button
          v-for="doc in DATASET_DOCS"
          :key="doc.id"
          class="sidebar-item sidebar-item-dataset"
          :class="{ active: selectedId === doc.id }"
          @click="selectedId = doc.id"
        >
          <span class="sidebar-item-ds-id">{{ doc.datasetId }}</span>
          <span class="sidebar-item-title">{{ t('dataset.' + doc.datasetId) }}</span>
        </button>
      </div>
    </aside>

    <!-- Main content -->
    <main class="docs-main">
      <div class="docs-content md-body" v-html="renderedContent"></div>
    </main>
  </div>
</template>

<style scoped>
.docs-layout {
  display: grid;
  grid-template-columns: 250px 1fr;
  gap: 2rem;
  align-items: start;
  min-height: calc(100vh - 120px);
}

@media (max-width: 900px) {
  .docs-layout {
    grid-template-columns: 1fr;
  }
}

/* Sidebar */
.docs-sidebar {
  position: sticky;
  top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.sidebar-group {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.sidebar-group-title {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vt-c-text-light-2);
  padding: 0 0.6rem 0.35rem;
}

.sidebar-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1rem;
  padding: 0.45rem 0.6rem;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: all var(--transition-fast);
  width: 100%;
}

.sidebar-item:hover {
  background: var(--color-background-soft);
}

.sidebar-item.active {
  background: rgba(0, 137, 122, 0.1);
}

.sidebar-item-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-heading);
  line-height: 1.3;
}

.sidebar-item.active .sidebar-item-title {
  color: var(--brand-accent-dark);
}

.sidebar-item-sub {
  font-size: 0.72rem;
  color: var(--vt-c-text-light-2);
  line-height: 1.3;
}

/* Dataset items – compact row */
.sidebar-item-dataset {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.sidebar-item-ds-id {
  font-size: 0.75rem;
  font-weight: 700;
  font-family: 'Fira Code', monospace;
  color: var(--brand-primary);
  background: var(--color-background-mute);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
  flex-shrink: 0;
  min-width: 2.4rem;
  text-align: center;
}

.sidebar-item-dataset.active .sidebar-item-ds-id {
  border-color: var(--brand-accent);
  color: var(--brand-accent-dark);
  background: rgba(0, 137, 122, 0.08);
}

/* Main content */
.docs-main {
  min-width: 0;
}

.docs-content {
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 2rem 2.25rem;
}
</style>

<!-- Unscoped markdown styles (v-html content) -->
<style>
.md-body h1.md-h1 {
  font-size: 1.6rem;
  font-weight: 800;
  color: var(--brand-primary);
  margin: 0 0 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--color-border);
}

.md-body h2.md-h2 {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--brand-primary);
  margin: 1.75rem 0 0.65rem;
  padding-bottom: 0.3rem;
  border-bottom: 1px solid var(--color-border);
}

.md-body h3.md-h3 {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-heading);
  margin: 1.25rem 0 0.5rem;
}

.md-body h4.md-h4,
.md-body h5.md-h5,
.md-body h6.md-h6 {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--color-heading);
  margin: 1rem 0 0.4rem;
}

.md-body p.md-p {
  font-size: 0.92rem;
  color: var(--color-text);
  line-height: 1.7;
  margin: 0 0 0.85rem;
}

.md-body ul.md-ul {
  margin: 0.5rem 0 0.85rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.md-body ul.md-ul li {
  font-size: 0.9rem;
  color: var(--color-text);
  line-height: 1.6;
}

.md-body hr.md-hr {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 1.5rem 0;
}

/* Tables */
.md-body table.md-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
  margin: 0.75rem 0 1.25rem;
}

.md-body table.md-table th {
  text-align: left;
  padding: 0.45rem 0.75rem;
  font-weight: 700;
  font-size: 0.78rem;
  color: var(--vt-c-text-light-2);
  background: var(--color-background-soft);
  border-bottom: 2px solid var(--color-border);
  white-space: nowrap;
}

.md-body table.md-table td {
  padding: 0.4rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
  vertical-align: top;
  color: var(--color-text);
  line-height: 1.5;
}

.md-body table.md-table tbody tr:hover {
  background: var(--color-background-soft);
}

/* Code blocks */
.md-body pre.md-pre {
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 1rem 1.1rem;
  overflow-x: auto;
  margin: 0.75rem 0 1.25rem;
}

.md-body pre.md-pre code {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--color-text);
  white-space: pre;
}

/* Inline code */
.md-body code.md-inline {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.82em;
  background: var(--color-background-mute);
  border: 1px solid var(--color-border);
  border-radius: 3px;
  padding: 0.1em 0.35em;
  color: var(--brand-primary);
}

/* Links */
.md-body a {
  color: var(--brand-accent-dark);
  text-decoration: underline;
}

.md-body a:hover {
  color: var(--brand-accent);
}
</style>
