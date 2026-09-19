import { useMemo } from 'react'
import { useT } from '../i18n'

/** Radar of the optional XAI axes from spec §4.2:
 *  - Pitch Stability %        : inverse-scaled jitter
 *  - Phase Continuity %       : 0..1 → 0..100
 *  - Noise-Floor Dropouts %  : capped + inverted so high dropouts → low score
 */
export function Radar({ ev, pfDropoutsMax = 8 }: { ev: any; pfDropoutsMax?: number }) {
  const t = useT()
  const p = (ev && ev.prosody) || {}
  const pitchStability = p.pitch_stability ?? 0
  const phaseContinuity = p.phase_continuity != null ? p.phase_continuity * 100 : 50
  const nfDropouts = p.noise_floor_dropouts != null ? p.noise_floor_dropouts : 0
  const items = useMemo(
    () => [
      { label: t('Pitch Stability'), value: pitchStability, color: '#2563EB' },
      { label: t('Phase Continuity'), value: phaseContinuity, color: '#7c5cbf' },
      { label: t('NF Dropouts'), value: 100 - Math.min(100, (nfDropouts / pfDropoutsMax) * 100), color: '#b45309' },
    ],
    [pitchStability, phaseContinuity, nfDropouts, pfDropoutsMax, t],
  )

  const cx = 4, cy = 4, R = 3.25
  const angle0 = -Math.PI / 2

  return (
    <div className="space-y-2.5">
      <div className="space-y-2">
        {items.map((it) => (
          <div key={it.label}>
            <div className="flex justify-between gap-2 text-[12.5px]">
              <span className="min-w-0 truncate text-zinc-800">{it.label}</span>
              <span className="shrink-0 font-mono text-zinc-500">{it.value.toFixed(0)}%</span>
            </div>
            <div className="mt-1 h-[3px] rounded-full bg-[#F1EEE9]">
              <div
                className="h-[3px] rounded-full"
                style={{
                  width: `${Math.min(100, it.value)}%`,
                  background: it.color,
                  transition: 'width 0.4s cubic-bezier(0.25, 0.1, 0.25, 1)',
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* radial spider */}
      <svg viewBox="0 0 800 800" className="mx-auto block w-40 max-w-full" aria-hidden="true">
        {items.map((it, i) => {
          const a = angle0 + (2 * Math.PI / items.length) * i
          const x = cx + Math.cos(a) * R
          const y = cy + Math.sin(a) * R
          return (
            <g key={it.label}>
              <line
                x1={cx * 100}
                y1={cy * 100}
                x2={x * 100}
                y2={y * 100}
                stroke="#E4E4E7"
                strokeWidth="2"
              />
              <circle cx={x * 100} cy={y * 100} r="3" fill={it.color} />
              <text
                x={(x * 100 + (x < 0 ? -14 : 14))}
                y={(y * 100 + 22)}
                textAnchor={x < 0 ? 'end' : 'start'}
                fill="#71717A"
                fontSize="22"
                fontFamily="Inter, sans-serif"
              >
                {it.label}
              </text>
            </g>
          )
        })}
        <circle cx={cx * 100} cy={cy * 100} r="8" fill="none" stroke="#E4E4E7" strokeWidth="2" />
        <circle cx={cx * 100} cy={cy * 100} r={R * 100} fill="none" stroke="#E4E4E7" strokeWidth="1.5" />
        {items.map((it, i) => {
          const a = angle0 + (2 * Math.PI / items.length) * i
          const r = Math.min(1, it.value / 100) * R
          const x = cx + Math.cos(a) * r
          const y = cy + Math.sin(a) * r
          return (
            <circle
              key={`pt-${i}`}
              cx={x * 100}
              cy={y * 100}
              r="9"
              fill={it.color}
              opacity="0.85"
              style={{ transition: 'cx 0.4s cubic-bezier(0.25, 0.1, 0.25, 1), cy 0.4s cubic-bezier(0.25, 0.1, 0.25, 1)' }}
            />
          )
        })}
      </svg>
    </div>
  )
}
