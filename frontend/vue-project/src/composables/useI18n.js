import { ref } from 'vue'
import et from '@/i18n/et.json'
import en from '@/i18n/en.json'

const messages = { et, en }
const locale = ref('et')

export function useI18n() {
  /**
   * Translate a dot-separated key, with optional {param} interpolation.
   *   t('results.loading')           → "Pipeline töötab..."
   *   t('mlPreview.showingFirst', { total: 48 })  → "Näidatakse esimesed 5 rida 48-st"
   */
  function t(key, params) {
    const keys = key.split('.')
    let val = messages[locale.value]
    for (const k of keys) {
      if (val == null) return key
      val = val[k]
    }
    if (typeof val !== 'string') return key
    if (params) {
      return val.replace(/\{(\w+)\}/g, (match, k) => (k in params ? params[k] : match))
    }
    return val
  }

  function setLocale(l) {
    if (messages[l]) {
      locale.value = l
      document.documentElement.lang = l
    }
  }

  return { t, locale, setLocale }
}
