import { useMemo, useState } from 'react'
import { Breadcrumbs, PageHeader, Divider, Sparkline, useLiveSession, btn } from '../components/ui'
import { RiskGauge, XaiBars } from '../components/RiskGauge'
import { Radar } from '../components/Radar'
import { ShieldBanner } from '../components/ShieldBanner'

const LANGS = ['en', 'hi', 'kn'] as const

export default function Dashboard({ liveOnly = false, onNavigate }: { liveOnly?: boolean; onNavigate: (v: string) => void }) {
  const live = useLiveSession()
  const [role, setRole] = useState<'adult' | 'child'>('adult')
  const [language, setLanguage] = useState<'en' | 'hi' | 'kn'>('en')
  const [speaker, setSpeaker] = useState('')


  if (liveOnly) {
    return (
      <article>
        <Breadcrumbs trail={['Monitoring', 'Live call monitor']} />
        <PageHeader
          title="Live call monitor"
          meta={
            <>
              Real-time stream analysis over WebSocket · 300 ms windows, 100 ms hop · PCM 16 kHz mono.{' '}
              <a className="underline decoration-[#E4E4E7] underline-offset-2 hover:decoration-zinc-400" href="#" onClick={(e) => { e.preventDefault(); onNavigate('dashboard') }}>
                Back to overview
              </a>
            </>
          }
          actions={
            !live.connected ? (
              <button
                className={btn('btn-primary')}
                onClick={() => live.connect({ role, language, speaker })}
              >
                Start session
              </button>
            ) : (
              <button className={btn()} onClick={live.sendEnd}>
                End session
              </button>
            )
          }
        />
        <Divider />
        <LivePanel
          live={live}
          role={role}
          setRole={setRole}
          language={language}
          setLanguage={setLanguage}
          speaker={speaker}
          setSpeaker={setSpeaker}
        />
      </article>
    )
  }

  return (
    <article>
      <Breadcrumbs trail={['Monitoring', 'Overview']} />
      <PageHeader
        title="Voice integrity, verified in real time."
        meta="VoiceShield analyzes live call audio for AI-generated speech — acoustic model, prosodic evidence and enterprise watermarking, fused into a single actionable score."
        actions={
          <>
            <button className={btn()} onClick={() => onNavigate('reports')}>
              View forensics
            </button>
            <button className={btn('btn-primary')} onClick={() => onNavigate('live')}>
              Start live session
            </button>
          </>
        }
      />
      <Divider />

      {/* Reading-column intro */}
      <div className="space-y-5 leading-relaxed text-zinc-700">
        <p>
          Every 300 milliseconds, VoiceShield extracts a fresh window from the call stream and runs it through three
          independent checks: a graph-attention acoustic model (AASIST-L), sub-phonemic prosodic analysis — jitter,
          shimmer and spectral phase continuity — and a watermark verifier that recognizes authorized enterprise
          callers instantly.
        </p>
        <p>
          The results are fused into a single <strong className="font-semibold text-zinc-900">synthetic score</strong>.
          Crossings trigger role-aware mitigation: 70% for calls involving children, 85% for adults, with alerts
          dispatched to Telegram, email, SMS and webhooks, and an I4C-ready forensic PDF generated for every incident.
        </p>
      </div>

      {/* Stat cards */}
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <StatCard label="Detection latency" value="< 50 ms" note="ONNX Runtime, 2 CPU threads" />
        <StatCard label="Window cadence" value="300 ms" note="100 ms sliding hop" />
        <StatCard label="Languages" value="EN · HI · KN" note="accent-invariant features" />
      </div>

      {/* Pipeline explainer */}
      <h2 className="mt-10 font-serif text-[24px] font-bold tracking-tight text-zinc-900">How a window is scored</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Step n="01" title="Watermark check" body="A 4096-point FFT scans 7.0–7.5 kHz for the enterprise pilot tone. A verified caller short-circuits the pipeline with a score of zero." />
        <Step n="02" title="Acoustic model" body="AASIST-L — a spectro-temporal graph attention network — classifies synthesis artifacts in the log-mel spectrogram." />
        <Step n="03" title="Prosodic XAI" body="Glottal-cycle jitter and shimmer plus inter-frame phase continuity expose the unnatural regularity of neural speech." />
      </div>

      {/* Threshold reference */}
      <h2 className="mt-10 font-serif text-[24px] font-bold tracking-tight text-zinc-900">Mitigation thresholds</h2>
      <div className="card mt-4 overflow-hidden">
        <table className="w-full text-left text-[13.5px]">
          <thead>
            <tr className="border-b border-[#E4E4E7] text-[11px] uppercase tracking-wide text-zinc-500">
              <th className="px-5 py-3 font-semibold">Scenario</th>
              <th className="px-5 py-3 font-semibold">Trigger</th>
              <th className="px-5 py-3 font-semibold">Response</th>
            </tr>
          </thead>
          <tbody>
            {[
              ['Child-safety calls', 'Score ≥ 70%', 'Immediate guardian alert, block sensitive actions'],
              ['Adult / enterprise calls', 'Score ≥ 85%', 'Hold transaction, require call-back or MFA'],
              ['Elevated suspicion', 'Score ≥ 35%', 'Warning banner, recommend secondary verification'],
              ['Enterprise watermark', 'Pilot tone 12× noise floor', 'Verified caller — score forced to 0.0'],
            ].map(([a, b, c]) => (
              <tr key={a} className="border-b border-[#F1EEE9] last:border-0 hover:bg-[#FAF8F5]">
                <td className="px-5 py-3 font-semibold text-zinc-900">{a}</td>
                <td className="px-5 py-3 font-mono text-[12.5px] text-zinc-600">{b}</td>
                <td className="px-5 py-3 text-zinc-600">{c}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Inline live mini-monitor */}
      <h2 className="mt-10 font-serif text-[24px] font-bold tracking-tight text-zinc-900">Quick check</h2>
      <p className="mt-1 text-[14px] text-zinc-500">
        Run a 30-second check from this page — or open the{' '}
        <a
          className="font-medium text-zinc-900 underline decoration-[#E4E4E7] underline-offset-2 hover:decoration-zinc-400"
          href="#"
          onClick={(e) => {
            e.preventDefault()
            onNavigate('live')
          }}
        >
          full live monitor
        </a>
        .
      </p>
      <div className="mt-4">
        <LivePanel
          live={live}
          role={role}
          setRole={setRole}
          language={language}
          setLanguage={setLanguage}
          speaker={speaker}
          setSpeaker={setSpeaker}
          compact
        />
      </div>
    </article>
  )
}

/* ------------------------------ Live panel --------------------------------- */

function LivePanel({ live, role, setRole, language, setLanguage, speaker, setSpeaker, compact = false }: any) {
  const { connected, micActive, events, latency, shielding, mitigation, setShielded, error } = live
  const analyses = useMemo(() => events.filter((e: any) => e.type === 'analysis'), [events])
  const latest = analyses.at(-1)
  const scores = analyses.map((a: any) => a.synthetic_score ?? 0)
  const peak = scores.length ? Math.max(...scores) : 0
  void scores
  void setShielded

  return (
    <div className={compact ? '' : 'grid gap-6 lg:grid-cols-[280px_1fr]'}>
      {/* Controls */}
      <div className="card h-fit p-5">
        <h3 className="text-[11px] font-bold uppercase tracking-wide text-zinc-500">Session setup</h3>
        <div className="mt-3 space-y-3.5">
          <Seg
            label="Role"
            options={['adult', 'child']}
            value={role}
            onChange={setRole}
            disabled={connected}
          />
          <Seg
            label="Language"
            options={[...LANGS]}
            value={language}
            onChange={setLanguage}
            disabled={connected}
            upper
          />
          <div>
            <label className="text-[12px] font-medium text-zinc-500">Enrolled speaker (optional)</label>
            <input
              value={speaker}
              disabled={connected}
              onChange={(e) => setSpeaker(e.target.value)}
              placeholder="e.g. manager_rajesh"
              className="mt-1 w-full rounded-lg border border-[#E4E4E7] bg-white px-3 py-2 text-[13.5px] text-zinc-900 outline-none transition-colors placeholder:text-zinc-400 focus:border-[#2563EB]"
            />
          </div>
          {!connected ? (
            <button
              className="btn-pill btn-primary w-full justify-center"
              onClick={() => live.connect({ role, language, speaker })}
            >
              Start live session
            </button>
          ) : (
            <button className="btn-pill w-full justify-center" onClick={live.sendEnd}>
              End session
            </button>
          )}
          <div className="flex items-center justify-center gap-1.5 text-[12px] text-zinc-500">
            <span
              className="live-dot h-1.5 w-1.5 rounded-full"
              style={{ background: connected ? (shielding ? '#C2410C' : '#2563EB') : '#D4D4D8' }}
            />
            {connected ? (shielding ? 'Shielded — mic paused' : micActive ? 'Microphone live' : 'Connected') : 'Offline'}
          </div>
          {error && (
            <p className="rounded-lg bg-[#FDF2F2] px-3 py-2 text-[12px] leading-relaxed text-[#DC2626]">{error}</p>
          )}
        </div>
      </div>

      {/* Gauge + timeline */}
      <div className="mt-4 space-y-4 lg:mt-0">
        <div className="grid items-stretch gap-4 md:grid-cols-[240px_1fr]">
          <div className="card flex items-center justify-center p-5">
            <RiskGauge score={latest?.synthetic_score ?? 0} band={latest?.risk_band ?? 'low'} />
          </div>
          <div className="card flex flex-col p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 className="text-[14px] font-bold text-zinc-900">Score timeline</h3>
              <span className="font-mono text-[12px] text-zinc-500">
                peak {(peak * 100).toFixed(0)}% · {analyses.length} windows · latency {latency.toFixed(0)} ms
              </span>
            </div>
            <div className="mt-3 flex-1">
              <Sparkline values={scores.length ? scores : [0]} height={96} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <MiniStat label="Model P" value={latest?.model_prob ?? 0} />
              <MiniStat label="XAI risk" value={latest?.xai_risk ?? 0} />
              <MiniStat label="Verdict" value={latest?.verdict ?? '—'} />
              <MiniStat label="NF drops" value={latest?.prosody?.noise_floor_dropouts ?? 0} />
            </div>
            {latest?.recommendation && (
              <p className="mt-3 text-[13px] leading-relaxed text-zinc-600">{latest.recommendation}</p>
            )}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="card p-5">
            <h3 className="text-[14px] font-bold text-zinc-900">XAI breakdown</h3>
            <p className="mb-3 text-[12px] text-zinc-500">Latest 300 ms window</p>
            <div className="grid items-start gap-4 sm:grid-cols-2">
              <XaiBars ev={latest} />
              <Radar ev={latest} />
            </div>
            {latest?.speaker_mismatch != null && (
              <p className="mt-3 text-[13px]" style={{ color: latest?.speaker_mismatch ? '#DC2626' : '#3f6f4f' }}>
                {latest?.speaker_mismatch
                  ? 'Speaker mismatch — possible impersonation.'
                  : 'Consistent with the enrolled voice.'}
              </p>
            )}
          </div>
          <div className="card p-5">
            <h3 className="text-[14px] font-bold text-zinc-900">Mitigation</h3>
            <p className="mb-3 text-[12px] text-zinc-500">Role-aware response (child ≥ 70% / adult ≥ 85%)</p>
            <MitigationPanel
              shielding={shielding}
              mitigation={mitigation}
              connected={connected}
              setShielded={setShielded}
            />
          </div>
        </div>
        {shielding && mitigation?.action === 'child_shield' && (
          <ShieldBanner mitigation={mitigation} onDismiss={() => setShielded(false)} />
        )}
      </div>
    </div>
  )
}

function MitigationPanel({ shielding, mitigation, connected, setShielded: _setShielded }: any) {
  if (shielding && mitigation?.action === 'child_shield') {
    return null
  }
  return (
    <>
      <p className="text-[13px] text-zinc-500">
        {connected
          ? 'Monitoring live — no mitigation triggered yet.'
          : 'Start a session to see role-aware mitigation.'}
      </p>
      {mitigation?.type === 'mitigation' && mitigation.action === 'risk_banner' ? (
        <div className="mt-3">
          <ShieldBanner mitigation={mitigation} />
        </div>
      ) : null}
    </>
  )
}

function Seg({ label, options, value, onChange, disabled, upper }: {
  label: string
  options: string[]
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  upper?: boolean
}) {
  return (
    <div>
      <label className="text-[12px] font-medium text-zinc-500">{label}</label>
      <div className="mt-1 flex gap-1.5">
        {options.map((o) => (
          <button
            key={o}
            disabled={disabled}
            onClick={() => onChange(o)}
            className={`flex-1 rounded-lg border px-2 py-1.5 text-[12.5px] font-semibold transition-colors ${
              value === o
                ? 'border-zinc-900 bg-zinc-900 text-white'
                : 'border-[#E4E4E7] bg-white text-zinc-700 hover:bg-[#F1EEE9]'
            } ${upper ? 'uppercase' : 'capitalize'}`}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  )
}

function MiniStat({ label, value, good }: { label: string; value: unknown; good?: boolean }) {
  return (
    <div className="min-w-0 rounded-lg bg-[#FAF8F5] px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">{label}</div>
      <div
        className="mt-0.5 truncate font-mono text-[13.5px] text-zinc-900"
        title={typeof value === 'number' ? value.toFixed(3) : String(value)}
        style={good ? { color: '#3f6f4f' } : undefined}
      >
        {typeof value === 'number' ? value.toFixed(3) : String(value)}
      </div>
    </div>
  )
}

function StatCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="card p-5">
      <div className="text-[11px] font-bold uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 font-serif text-[26px] font-bold tracking-tight text-zinc-900">{value}</div>
      <div className="mt-0.5 text-[12.5px] text-zinc-500">{note}</div>
    </div>
  )
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="card p-5">
      <div className="font-mono text-[12px] font-semibold text-[#2563EB]">{n}</div>
      <h3 className="mt-1 text-[15px] font-bold text-zinc-900">{title}</h3>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-zinc-600">{body}</p>
    </div>
  )
}
