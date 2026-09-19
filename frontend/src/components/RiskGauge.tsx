import { useMemo } from 'react'
import { useT } from '../i18n'

export function bandColor(band?: string): string {
  if (band === 'critical' || band === 'high') return '#DC2626'
  if (band === 'medium') return '#b45309'
  return '#3f6f4f'
}

/** Circular risk gauge — serif numeral, editorial styling. */
export function RiskGauge({ score, band }: { score: number; band: string }) {
  const t = useT()
  const R = 74
  const CIRC = 2 * Math.PI * R
  const frac = Math.max(0, Math.min(1, score))
  const color = bandColor(band)
  return (
    <div className="flex flex-col items-center">
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={R} fill="none" stroke="#F1EEE9" strokeWidth="9" />
        <circle
          cx="90"
          cy="90"
          r={R}
          fill="none"
          stroke={color}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={`${frac * CIRC} ${CIRC}`}
          transform="rotate(-90 90 90)"
          style={{ transition: 'stroke-dasharray 0.5s cubic-bezier(0.25, 0.1, 0.25, 1), stroke 0.3s ease' }}
        />
        <text
          x="90"
          y="92"
          textAnchor="middle"
          fontSize="40"
          fontWeight="700"
          fill="#18181B"
          fontFamily="Georgia, serif"
          style={{ letterSpacing: '-0.02em' }}
        >
          {(score * 100).toFixed(0)}
        </text>
        <text x="90" y="114" textAnchor="middle" fontSize="10.5" fill="#71717A" style={{ letterSpacing: '0.08em' }}>
          {t('SYNTHETIC SCORE')}
        </text>
      </svg>
      <div className="mt-1.5 text-[12px] font-semibold capitalize" style={{ color }}>
        {t('{band} risk', { band: t(`band.${band}`) })}
      </div>
    </div>
  )
}

/** Per-window XAI factor bars — editorial rows. */
export function XaiBars({ ev }: { ev: any }) {
  const t = useT()
  const rows = useMemo(() => {
    const p = (ev && ev.prosody) || {}
    const num = (v: any, fallback = 0) => (typeof v === 'number' ? v : fallback)
    return [
      { label: t('Model P(synthetic)'), v: num(ev?.model_prob), max: 1, color: '#2563EB' },
      { label: t('XAI risk (fused)'), v: num(ev?.xai_risk), max: 1, color: '#7c5cbf' },
      { label: t('Phase discontinuity'), v: 1 - (p.phase_continuity ?? 1), max: 1, color: '#b45309' },
      { label: t('Jitter'), v: num(p.jitter_pct), max: 2.5, color: '#71717A', fmt: (v: number) => `${v.toFixed(3)}%` },
      { label: t('Shimmer'), v: num(p.shimmer_pct), max: 6, color: '#71717A', fmt: (v: number) => `${v.toFixed(3)}%` },
    ]
  }, [ev, t])
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="flex justify-between gap-2 text-[12.5px]">
            <span className="min-w-0 truncate text-zinc-800">{r.label}</span>
            <span className="shrink-0 font-mono text-zinc-500">
              {r.fmt ? r.fmt(r.v) : `${((r.v / r.max) * 100).toFixed(0)}%`}
            </span>
          </div>
          <div className="mt-1 h-[3px] rounded-full bg-[#F1EEE9]">
            <div
              className="h-[3px] rounded-full"
              style={{
                width: `${Math.min(100, (r.v / r.max) * 100)}%`,
                background: r.color,
                transition: 'width 0.4s cubic-bezier(0.25, 0.1, 0.25, 1)',
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
