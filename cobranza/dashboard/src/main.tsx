import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import { ConversationProvider } from '@elevenlabs/react'
import './tailwind.css'
import './brand.css'
import './index.css'
import './site.css'
import { I18nProvider } from './I18nProvider'
import { Layout } from './site/Layout'
import Console from './pages/Console'
import Home from './pages/Home'
import UseCases from './pages/UseCases'
import CaseDetail from './pages/CaseDetail'
import HowItWorks from './pages/HowItWorks'
import Integration from './pages/Integration'
import Demo from './pages/Demo'
import Deck from './pages/Deck'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <ConversationProvider>
        <BrowserRouter>
          <Routes>
            <Route path="presentacion/:slide?" element={<Deck />} />
            <Route element={<Layout />}>
              <Route index element={<Home />} />
              <Route path="casos" element={<UseCases />} />
              <Route path="casos/:id" element={<CaseDetail />} />
              <Route path="como-funciona" element={<HowItWorks />} />
              <Route path="integracion" element={<Integration />} />
              <Route path="demo/:id" element={<Demo />} />
              <Route path="consola" element={<Console />} />
              <Route path="*" element={<Home />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ConversationProvider>
    </I18nProvider>
  </StrictMode>,
)
