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

/** Recharts-free sparkline (SVG polyline) — zero extra deps. */
export function Sparkline({ values, color = '#2563EB', height = 48 }: { values: number[]; color?: string; height?: number }) {
  const w = 240
  const max = Math.max(...values, 0.001)
  const pts = values
    .map((v, i) => `${(i / Math.max(values.length - 1, 1)) * w},${height - (v / max) * (height - 4) - 2}`)
    .join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" />
    </svg>
  )
}

/** Hook: live WebSocket session with mic capture (or simulated fallback). */
export function useLiveSession() {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [micActive, setMicActive] = useState(false)
  const [latency, setLatency] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const audioRef = useRef<{ ctx: AudioContext; stream: MediaStream; proc: ScriptProcessorNode } | null>(null)
  const [shielding, setShielding] = useState(false)
  const [mitigation, setMitigation] = useState<any>(null)

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

  const connect = (opts: { role: string; language: string; speaker: string }) => {
    const q = new URLSearchParams({ role: opts.role, language: opts.language, speaker: opts.speaker })
    const ws = new WebSocket(`${wsBase()}/ws/stream/demo-${Date.now().toString(36)}?${q}`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setShielded(false)
      setMicActive(false)
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

    // capture mic → int16 PCM @16 kHz → 100 ms chunks
    navigator.mediaDevices
      ?.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      .then((stream) => {
        const ctx = new AudioContext({ sampleRate: 16000 })
        const src = ctx.createMediaStreamSource(stream)
        const proc = ctx.createScriptProcessor(1600, 1, 1) // 100 ms
        proc.onaudioprocess = (e) => {
          const f = e.inputBuffer.getChannelData(0)
          const buf = new Int16Array(f.length)
          for (let i = 0; i < f.length; i++) {
            const s = Math.max(-1, Math.min(1, f[i]))
            buf[i] = s < 0 ? s * 0x8000 : s * 0x7fff
          }
          if (ws.readyState === WebSocket.OPEN) ws.send(buf.buffer)
        }
        src.connect(proc)
        proc.connect(ctx.destination) // required for ScriptProcessor to fire
        audioRef.current = { ctx, stream, proc }
        setMicActive(true)
      })
      .catch(() => setMicActive(false))
  }

  const sendEnd = () => {
    wsRef.current?.send(JSON.stringify({ type: 'end' }))
    wsRef.current?.close()
    setConnected(false)
    setShielded(false)
    setMicActive(false)
  }

  useEffect(() => () => {
    wsRef.current?.close()
    audioRef.current?.proc.disconnect()
    audioRef.current?.stream.getTracks().forEach((t) => t.stop())
    audioRef.current?.ctx.close()
    audioRef.current = null
  }, [])

  return { connected, micActive, events, latency, connect, sendEnd, shielding, mitigation, setShielded } as const
}
