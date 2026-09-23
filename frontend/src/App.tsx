import { useState } from 'react'
import { TopBar, Sidebar, type NavSection } from './components/ui'
import Dashboard from './pages/Dashboard'
import Incidents from './pages/Incidents'
import Reports from  './pages/Reports'
import { LanguageProvider, useT } from './i18n'
import { apiBase } from './components/ui'
import ProjectWorking from './pages/ProjectWorking'

type View =
  | 'dashboard'
  | 'live'
  | 'incidents'
  | 'reports'
  | 'blockchain'
  | 'analyze'
  | 'speakers'
  | 'project'

function AppInner() {
  const t = useT()
  const [view, setView] = useState<View>('dashboard')
  const nav = (v: string) => setView(v as View)

  const SECTIONS: NavSection[] = [
    {
      id: 'monitoring',
      label: t('Monitoring'),
      items: [
        { id: 'dashboard', label: t('Overview') },
        { id: 'live', label: t('Live call monitor') },
      ],
    },
    {
      id: 'risk',
      label: t('Risk & incidents'),
      items: [{ id: 'incidents', label: t('Incident log') }],
    },
    {
      id: 'forensics',
      label: t('Forensics'),
      items: [
        { id: 'reports', label: t('Session forensics') },
        { id: 'blockchain', label: t('Blockchain ledger') },
        { id: 'analyze', label: t('File analysis') },
      ],
    },
    {
      id: 'identity',
      label: t('Identity'),
      items: [{ id: 'speakers', label: t('Speaker enrollment') }],
    },
    {
      id: 'about',
      label: 'Project Working',
      items: [{ id: 'project', label: 'Project Working' }],
    },
  ]

  return (
    <div className="min-h-screen">
      <TopBar onNav={(id) => setView(id as View)} />
      <div className="mx-auto flex max-w-[1400px]">
        <Sidebar sections={SECTIONS} active={view} onNavigate={nav} />
        <main className="min-w-0 flex-1 px-6 py-8 md:px-10 lg:px-12">
          <div className="mx-auto max-w-3xl">
            {view === 'dashboard' && <Dashboard onNavigate={nav} />}
            {view === 'live' && <Dashboard liveOnly onNavigate={nav} />}
            {view === 'incidents' && <Incidents />}
            {view === 'reports' && <Reports initialTab="sessions" />}
            {view === 'blockchain' && <Reports initialTab="blockchain" />}
            {view === 'analyze' && <Reports initialTab="analyze" />}
            {view === 'speakers' && <Reports initialTab="speakers" />}
            {view === 'project' && <ProjectWorking />}
          </div>
        </main>
      </div>
      <footer className="border-t border-[#E4E4E7] py-6">
        <p className="mx-auto max-w-[1400px] px-6 text-center text-[12.5px] text-zinc-500">
          {t(
            'VoiceShield AI — real-time voice integrity verification · AASIST-L inference, prosodic XAI, watermark verification · API served from {base}',
            { base: apiBase() || t('this origin') }
          )}
        </p>
      </footer>
    </div>
  )
}

export default function App() {
  return (
    <LanguageProvider>
      <AppInner />
    </LanguageProvider>
  )
}
