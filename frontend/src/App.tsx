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
  const [sub, setSub] = useState<string>('solution')
  const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const PROJECT_SUBS = ['solution', 'approach', 'feasibility', 'impacts', 'references']

  const nav = (v: string) => {
    if (PROJECT_SUBS.includes(v)) {
      setView('project')
      setSub(v)
      requestAnimationFrame(() => {
        document.getElementById(v)?.scrollIntoView({ behavior: reduceMotion() ? 'auto' : 'smooth', block: 'start' })
      })
      return
    }
    if (v === 'project') {
      setView('project')
      setSub('solution')
      window.scrollTo({ top: 0, behavior: reduceMotion() ? 'auto' : 'smooth' })
      return
    }
    setView(v as View)
  }

  const activeNav: string =
    view === 'project'
      ? sub
      : view === 'reports' || view === 'blockchain' || view === 'analyze'
        ? 'forensics'
        : view

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
      landing: 'reports',
      items: [],
    },
    {
      id: 'identity',
      label: t('Identity'),
      items: [{ id: 'speakers', label: t('Speaker enrollment') }],
    },
    {
      id: 'project',
      label: 'Project Working',
      landing: 'project',
      items: [
        { id: 'solution', label: 'Proposed solution' },
        { id: 'approach', label: 'Technical approach' },
        { id: 'feasibility', label: 'Feasibility & viability' },
        { id: 'impacts', label: 'Impacts & benefits' },
        { id: 'references', label: 'Research & references' },
      ],
    },
  ]

  return (
    <div className="min-h-screen">
      <TopBar onNav={(id) => setView(id as View)} />
      <div className="mx-auto flex max-w-[1400px]">
        <Sidebar sections={SECTIONS} active={activeNav} onNavigate={nav} />
        <main className="min-w-0 flex-1 px-6 py-8 md:px-10 lg:px-12">
          <div className="mx-auto max-w-3xl">
            {view === 'dashboard' && <Dashboard onNavigate={nav} />}
            {view === 'live' && <Dashboard liveOnly onNavigate={nav} />}
            {view === 'incidents' && <Incidents />}
            {view === 'reports' && <Reports key="sessions" initialTab="sessions" />}
            {view === 'blockchain' && <Reports key="blockchain" initialTab="blockchain" />}
            {view === 'analyze' && <Reports key="analyze" initialTab="analyze" />}
            {view === 'speakers' && <Reports key="speakers" initialTab="speakers" />}
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
