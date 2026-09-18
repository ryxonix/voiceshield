import { useState } from 'react'
import { TopBar, Sidebar, type NavSection } from './components/ui'
import Dashboard from './pages/Dashboard'
import Incidents from './pages/Incidents'
import Reports from './pages/Reports'
import { apiBase } from './lib'

type View = 'dashboard' | 'live' | 'session' | 'incidents' | 'incident' | 'reports' | 'analyze' | 'speakers'

const SECTIONS: NavSection[] = [
  {
    id: 'monitoring',
    label: 'Monitoring',
    items: [
      { id: 'dashboard', label: 'Overview' },
      { id: 'live', label: 'Live call monitor' },
    ],
  },
  {
    id: 'risk',
    label: 'Risk & incidents',
    items: [{ id: 'incidents', label: 'Incident log' }],
  },
  {
    id: 'forensics',
    label: 'Forensics',
    items: [
      { id: 'reports', label: 'Session forensics' },
      { id: 'analyze', label: 'File analysis' },
    ],
  },
  {
    id: 'identity',
    label: 'Identity',
    items: [{ id: 'speakers', label: 'Speaker enrollment' }],
  },
]

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const nav = (v: string) => setView(v as View)

  return (
    <div className="min-h-screen">
      <TopBar active={view === 'live' ? 'dashboard' : view} onNav={(id) => setView(id as View)} />
      <div className="mx-auto flex max-w-[1400px]">
        <Sidebar sections={SECTIONS} active={view} onNavigate={nav} />
        <main className="min-w-0 flex-1 px-6 py-8 md:px-10 lg:px-12">
          <div className="mx-auto max-w-3xl">
            {view === 'dashboard' && <Dashboard onNavigate={nav} />}
            {view === 'live' && <Dashboard liveOnly onNavigate={nav} />}
            {view === 'incidents' && <Incidents />}
            {view === 'reports' && <Reports initialTab="sessions" />}
            {view === 'analyze' && <Reports initialTab="analyze" />}
            {view === 'speakers' && <Reports initialTab="speakers" />}
          </div>
        </main>
      </div>
      <footer className="border-t border-[#E4E4E7] py-6">
        <p className="mx-auto max-w-[1400px] px-6 text-center text-[12.5px] text-zinc-500">
          VoiceShield AI — real-time voice integrity verification · AASIST-L inference, prosodic XAI, watermark
          verification · API served from {apiBase() || 'this origin'}
        </p>
      </footer>
    </div>
  )
}
