import { useEffect, useState, type ReactNode } from 'react'
import { I18nContext, i18nFor, initialLang, storeLang, type Lang } from './i18n'

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState(initialLang)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const choose = (next: Lang) => {
    storeLang(next)
    setLang(next)
  }
  return <I18nContext value={i18nFor(lang, choose)}>{children}</I18nContext>
}
