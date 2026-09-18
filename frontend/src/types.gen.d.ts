/// <reference types="vite/client" />

export interface LiveSessionReturn {
  connected: boolean
  micActive: boolean
  events: any[]
  connect(opts: { role: string; language: string; speaker: string }): void
  sendEnd(): void
  shielding: boolean
  mitigation: any
  setShielded(on: boolean, mitigationEvent?: any): void
  stop: () => void
}

export interface XaiEvent {
  t_ms?: number
  synthetic_score?: number
  model_prob?: number
  xai_risk?: number
  verdict?: string
  risk_band?: string
  recommendation?: string
  speaker_mismatch?: boolean | null
  latency_ms?: number
  prosody?: {
    jitter_pct?: number
    shimmer_pct?: number
    phase_continuity?: number
    pitch_stability?: number
    noise_floor_dropouts?: number
    watermark_snr?: number
  }
  watermark_hit?: boolean
}

export interface SegOptions {
  label: string
  options: string[]
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  upper?: boolean
}

export interface MiniStatProps {
  label: string
  value: unknown
  good?: boolean
}

export interface StatCardProps {
  label: string
  value: string
  note: string
}

export interface StepProps {
  n: string
  title: string
  body: string
}

export interface MitigationPanelProps {
  shielding: boolean
  mitigation: any
  connected: boolean
  setShielded: (on: boolean, mitigationEvent?: any) => void
}

export interface LivePanelProps {
  compact?: boolean
  connected: boolean
  micActive: boolean
  analyses: any[]
  latest: any
  scores: number[]
  peak: number
  events: any[]
  role: string
  setRole: (v: string) => void
  language: string
  setLanguage: (v: string) => void
  speaker: string
  setSpeaker: (v: string) => void
  connect: (opts: { role: string; language: string; speaker: string }) => void
  sendEnd: () => void
  shielding?: boolean
  mitigation?: any
  setShielded?: (on: boolean, mitigationEvent?: any) => void
}

export interface ShieldBannerProps {
  mitigation?: any
  onDismiss?: () => void
}
