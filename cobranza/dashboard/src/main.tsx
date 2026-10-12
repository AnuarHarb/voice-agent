import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConversationProvider } from '@elevenlabs/react'
import '@fontsource-variable/public-sans'
import './tailwind.css'
import './index.css'
import App from './App.tsx'
import { I18nProvider } from './I18nProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <ConversationProvider>
        <App />
      </ConversationProvider>
    </I18nProvider>
  </StrictMode>,
)
