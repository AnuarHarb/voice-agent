import { useI18n, type Lang } from '../i18n'

const LANGUAGES: { id: Lang; name: string }[] = [{ id: 'es', name: 'Español' }, { id: 'en', name: 'English' }]

export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n()
  return (
    <div className="lang-switch" role="group" aria-label={t.languageGroup}>
      {LANGUAGES.map((l) => (
        <button key={l.id} type="button" lang={l.id} aria-pressed={l.id === lang} onClick={() => setLang(l.id)}>
          {l.name}
        </button>
      ))}
    </div>
  )
}
