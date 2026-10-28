import { useI18n } from '../i18n'
import type { L10n, L10nList } from './useCases'

/** Pick the active language out of an {es, en} pair. */
export function useL() {
  const { lang } = useI18n()
  return {
    lang,
    l: (text: L10n) => text[lang],
    list: (items: L10nList) => items[lang],
  }
}
