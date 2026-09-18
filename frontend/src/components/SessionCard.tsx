import { bandColor } from './RiskGauge'

export function SessionCard({ s, onClick, active }: { s: any; onClick?: () => void; active?: boolean }) {
  const band =
    s.max_score >= 0.85 ? 'critical' : s.max_score >= 0.68 ? 'high' : s.max_score >= 0.35 ? 'medium' : 'low'
  const color = bandColor(band)
  return (
    <button
      onClick={onClick}
      className="w-full rounded-xl border p-3.5 text-left transition-colors hover:border-zinc-300"
      style={{ background: active ? '#fff' : 'transparent', borderColor: active ? '#18181B' : '#E4E4E7' }}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[12.5px] text-zinc-800">{s.call_id}</span>
        <span className="text-[14px] font-bold" style={{ color }}>
          {(s.max_score * 100).toFixed(0)}%
        </span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[11.5px] text-zinc-500">
        <span className="capitalize">{s.role}</span>
        <span className="uppercase">{s.language}</span>
        <span>{s.window_count} windows</span>
        {s.enterprise_verified && <span style={{ color: '#3f6f4f' }}>✓ enterprise</span>}
        {s.status === 'active' && (
          <span className="live-dot inline-flex items-center gap-1 font-semibold" style={{ color: '#2563EB' }}>
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: '#2563EB' }} />
            live
          </span>
        )}
      </div>
    </button>
  )
}
