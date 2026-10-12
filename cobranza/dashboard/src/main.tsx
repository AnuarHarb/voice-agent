import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConversationProvider } from '@elevenlabs/react'
import '@fontsource-variable/public-sans'
import './tailwind.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConversationProvider>
      <App />
    </ConversationProvider>
  </StrictMode>,
)
