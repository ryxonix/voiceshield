import { useEffect, useRef, useState } from 'react'

function readEnvBaseTrimmed(): string {
  const env = (import.meta as any).env ?? {}
  const raw = (env as any).VITE_API_BASE
  return typeof raw === 'string' ? raw.trim() : ''
}

export function apiBase(): string {
  const base = readEnvBaseTrimmed()
  if (!base) {
    const { protocol, hostname, port } = window.location
    if (port === '5173' || port === '5174' || port === '4173') return `${protocol}//${hostname}:8000`
    return ''
  }
  return base.replace(/\/$/, '')
}

export function wsBase(): string {
  const wsEnvBase = readEnvBaseTrimmed()
  if (!wsEnvBase) {
    const { protocol, hostname, port } = window.location
    if (port === '5173' || port === '5174' || port === '4173') return `ws://${hostname}:8000`
    return `${protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`
  }
  return wsEnvBase.replace(/^http/, 'ws').replace(/\/$/, '')
}

/* ------------------------------ Button helper ------------------------------ */
export const btn = (extra = '') => `btn-pill ${extra}`.trim()

/* --------------------------------- Icons ---------------------------------- */
export const Chevron = ({ open, className = '' }: { open?: boolean; className?: string }) => (
  <svg
    viewBox="0 0 16 16"
    width="14"
    height="14"
    className={`transition-transform duration-200 ${open ? 'rotate-90' : ''} ${className}`}
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M6 3.5 10.5 8 6 12.5" />
  </svg>
)
export const Caret = () => (
  <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 6l4 4 4-4" />
  </svg>
)
export const Globe = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4">
    <circle cx="8" cy="8" r="6.2" />
    <path d="M1.8 8h12.4M8 1.8c-4.2 4-4.2 8.4 0 12.4 4.2-4 4.2-8.4 0-12.4z" />
  </svg>
)

/** Vector VS monogram brand mark — blue. */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-label="VoiceShield logo">
      <rect width="32" height="32" rx="8" fill="#2563EB" />
      <path
        d="M8.5 8.5 12.6 22l3.4-9.4L19.4 22l4.1-13.5"
        stroke="#fff"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M23.5 8.5h-4.2" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}

/* ------------------------------ Top bar header ----------------------------- */
export function TopBar({
  right,
  onNav,
  active,
}: {
  right?: React.ReactNode
  onNav?: (id: string) => void
  active?: string
}) {
  const links = [
    { id: 'dashboard', label: 'Live Monitor' },
    { id: 'incidents', label: 'Incidents' },
    { id: 'reports', label: 'Forensics' },
  ]
  return (
    <header className="sticky top-0 z-30 border-b border-[#E4E4E7] bg-[#FAF8F5]/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-6">
        <button onClick={() => onNav?.('dashboard')} className="flex items-center gap-2.5">
          <BrandMark />
          <span className="text-[19px] font-bold tracking-tight text-zinc-900">
            VoiceShield <span className="font-serif font-semibold italic">AI</span>
          </span>
        </button>
        <div className="flex items-center gap-6">
          <nav className="hidden items-center gap-5 md:flex">
            {links.map((l) => (
              <button
                key={l.id}
                onClick={() => onNav?.(l.id)}
                className={`text-[14px] transition-opacity hover:opacity-70 ${
                  active === l.id ? 'font-semibold text-zinc-900' : 'font-medium text-zinc-600'
                }`}
              >
                {l.label}
              </button>
            ))}
          </nav>
          {right ?? <SettingsMenu />}
        </div>
      </div>
    </header>
  )
}

function SettingsMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-full border border-[#E4E4E7] bg-white px-3.5 py-1.5 text-[13px] font-medium text-zinc-800 transition-colors hover:bg-[#F1EEE9]"
      >
        <Globe />
        English
        <Caret />
      </button>
      {open && (
        <div className="rise absolute right-0 mt-2 w-48 rounded-xl border border-[#E4E4E7] bg-white p-1.5 shadow-lg shadow-zinc-900/5">
          {['English', 'हिन्दी', 'ಕನ್ನಡ'].map((l, i) => (
            <button
              key={l}
              onClick={() => setOpen(false)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-[13px] transition-colors hover:bg-[#F1EEE9] ${
                i === 0 ? 'font-semibold text-zinc-900' : 'text-zinc-700'
              }`}
            >
              {l}
              {i === 0 && <span className="text-[#2563EB]">●</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ------------------------------ Sidebar shell ------------------------------ */
export type NavItem = { id: string; label: string; badge?: string }
export type NavSection = { id: string; label: string; items: NavItem[] }

export function Sidebar({
  sections,
  active,
  onNavigate,
  header,
}: {
  sections: NavSection[]
  active: string
  onNavigate: (id: string) => void
  header?: React.ReactNode
}) {
  const [openSet, setOpenSet] = useState<Set<string>>(
    () => new Set(sections.filter((s) => s.items.some((i) => i.id === active)).map((s) => s.id)),
  )
  const toggle = (id: string) =>
    setOpenSet((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-64 shrink-0 overflow-y-auto border-r border-[#E4E4E7] pb-10 pt-6 lg:block">
      {header && <div className="px-5 pb-4">{header}</div>}
      <nav className="space-y-0.5 px-3">
        {sections.map((s) => {
          const open = openSet.has(s.id)
          return (
            <div key={s.id} className="mb-1">
              <button
                onClick={() => toggle(s.id)}
                className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[13.5px] font-bold text-zinc-900 transition-colors hover:bg-[#F1EEE9]"
              >
                <span>{s.label}</span>
                <span className="text-zinc-400">
                  <Chevron open={open} />
                </span>
              </button>
              {open && (
                <div className="mb-2 ml-3 mt-0.5 space-y-0.5 border-l border-[#E4E4E7] pl-2">
                  {s.items.map((i) => {
                    const isActive = i.id === active
                    return (
                      <button
                        key={i.id}
                        onClick={() => onNavigate(i.id)}
                        className={`flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-left text-[13.5px] transition-colors ${
                          isActive
                            ? 'bg-white font-semibold text-zinc-900 shadow-sm shadow-zinc-900/5 ring-1 ring-[#E4E4E7]'
                            : 'font-medium text-zinc-600 hover:bg-[#F1EEE9] hover:text-zinc-900'
                        }`}
                      >
                        <span>{i.label}</span>
                        {i.badge && (
                          <span className="rounded-full bg-[#FCEEE7] px-1.5 py-0.5 text-[10px] font-bold text-[#C2410C]">
                            {i.badge}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </aside>
  )
}

/* ------------------------------ Page scaffold ------------------------------ */
export function Breadcrumbs({ trail }: { trail: string[] }) {
  return (
    <nav className="flex flex-wrap items-center gap-1.5 text-[13px] text-zinc-500">
      {trail.map((t, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <Chevron className="text-zinc-300" />}
          <span className={i === trail.length - 1 ? 'text-zinc-700' : ''}>{t}</span>
        </span>
      ))}
    </nav>
  )
}

export function PageHeader({
  title,
  meta,
  actions,
}: {
  title: string
  meta?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        <h1 className="font-serif text-[34px] font-bold leading-tight tracking-tight text-zinc-900 md:text-[40px]">
          {title}
        </h1>
        {meta && <div className="mt-2 text-[13.5px] text-zinc-500">{meta}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Divider() {
  return <div className="my-7 border-b border-[#E4E4E7]" />
}

/* -------------------------------- Sparkline -------------------------------- */
export function Sparkline({
  values,
  color = '#2563EB',
  height = 56,
}: {
  values: number[]
  color?: string
  height?: number
}) {
  const w = 600
  const max = Math.max(...values, 0.001)
  const pts = values
    .map((v, i) => `${(i / Math.max(values.length - 1, 1)) * w},${height - (v / max) * (height - 4) - 2}`)
    .join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="block w-full" style={{ height }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

/* ------------------------------ Live WS hook ------------------------------- */
type HookReturn = {
  connected: boolean
  micActive: boolean
  events: any[]
  latency: number
  connect: (opts: { role: string; language: string; speaker: string }) => void
  sendEnd: () => void
  shielding: boolean
  mitigation: any
  error: string | null
  setShielded: (on: boolean, mitigationEvent?: any) => void
  stop: () => void
}

export function useLiveSession(): HookReturn {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [micActive, setMicActive] = useState(false)
  const [latency, setLatency] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const audioRef = useRef<{ ctx: AudioContext; stream: MediaStream; proc: ScriptProcessorNode } | null>(null)
  const [shielding, setShielding] = useState(false)
  const [mitigation, setMitigation] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const setShielded = (on: boolean, mitigationEvent?: any) => {
    setShielding(on)
    setMitigation(mitigationEvent ?? null)
    if (on) {
      audioRef.current?.stream.getTracks().forEach((t) => t.stop())
      setMicActive(false)
    } else {
      setMitigation(null)
    }
  }

  const stop = () => {
    try {
      audioRef.current?.proc?.disconnect()
      audioRef.current?.stream?.getTracks().forEach((t) => t.stop())
      audioRef.current?.ctx?.close()
    } catch {
      /* already closed */
    }
    audioRef.current = null
    setMicActive(false)
  }

  const connect = (opts: { role: string; language: string; speaker: string }) => {
    setError(null)
    setEvents([])
    const q = new URLSearchParams({ role: opts.role, language: opts.language, speaker: opts.speaker })
    const ws = new WebSocket(`${wsBase()}/ws/stream/demo-${Date.now().toString(36)}?${q}`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws
    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }
    ws.onerror = () => setError('WebSocket error — is the backend running on :8000?')
    ws.onclose = () => {
      setConnected(false)
      setShielded(false)
      stop()
    }
    ws.onmessage = (m) => {
      try {
        const ev = JSON.parse(m.data)
        setEvents((prev) => [...prev.slice(-199), ev])
        setLatency((ev as any).latency_ms ?? 0)
        if (ev?.type === 'mitigation' && ev?.action === 'child_shield') {
          setShielded(true, ev)
        }
      } catch {
        /* ignore */
      }
    }

    try {
      // Created synchronously inside the click gesture so the context runs;
      // created inside the promise callback it stays "suspended" and produces no audio.
      const ctx = new AudioContext()
      audioRef.current = { ctx, stream: null as unknown as MediaStream, proc: null as unknown as ScriptProcessorNode }
      navigator.mediaDevices
        ?.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
        .then(async (stream) => {
          if (ctx.state === 'suspended') {
            try {
              await ctx.resume()
            } catch { /* context may already be running */ }
          }
          if (ctx.state !== 'running') {
            setError('Microphone context could not start — allow mic permission and retry.')
            return
          }
          const src = ctx.createMediaStreamSource(stream)
          const proc = ctx.createScriptProcessor(1024, 1, 1)
          proc.onaudioprocess = (e) => {
            const data = e.inputBuffer.getChannelData(0)
            const buf = new Int16Array(data.length)
            for (let i = 0; i < data.length; i++) {
              const s = Math.max(-1, Math.min(1, data[i]))
              buf[i] = s < 0 ? s * 0x8000 : s * 0x7fff
            }
            if (ws.readyState === WebSocket.OPEN) ws.send(buf.buffer)
          }
          src.connect(proc)
          const g = ctx.createGain()
          g.gain.value = 0
          proc.connect(g)
          g.connect(ctx.destination)
          audioRef.current = { ctx, stream, proc }
          setMicActive(true)
          setError(null)
        })
        .catch((e) => {
          setMicActive(false)
          setError(`Microphone unavailable — ${e instanceof Error ? e.message : 'permission denied'}`)
        })
    } catch (e) {
      setError(`Audio init failed — ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const sendEnd = () => {
    wsRef.current?.send(JSON.stringify({ type: 'end' }))
    wsRef.current?.close()
    setConnected(false)
    setShielded(false)
    stop()
  }

  useEffect(() => () => {
    wsRef.current?.close()
    stop()
  }, [])

  return { connected, micActive, events, latency, connect, sendEnd, shielding, mitigation, error, setShielded, stop } as HookReturn
}
