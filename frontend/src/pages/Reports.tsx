import { useEffect, useMemo, useState } from 'react'
import { Breadcrumbs, PageHeader, Divider, Sparkline, apiBase, btn } from '../components/ui'
import { SessionCard } from '../components/SessionCard'

type Tab = 'sessions' | 'blockchain' | 'analyze' | 'speakers'

export default function Reports({ initialTab = 'sessions' }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab as Tab)
  useEffect(() => setTab(initialTab as Tab), [initialTab])

  const tabs: { id: Tab; label: string }[] = [
    { id: 'sessions', label: 'Session forensics' },
    { id: 'blockchain', label: 'Blockchain ledger' },
    { id: 'analyze', label: 'File analysis' },
    { id: 'speakers', label: 'Speaker enrollment' },
  ]

  return (
    <article>
      <Breadcrumbs trail={['Forensics', tabs.find((t) => t.id === tab)?.label || '']} />
      <PageHeader
        title="Forensics"
        meta="Reconstruct any monitored call window-by-window, run batch analysis on recordings, or enroll trusted voices for cross-session identity checks."
        actions={
          <div className="flex rounded-full border border-[#E4E4E7] bg-white p-0.5">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors ${
                  tab === t.id ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-[#F1EEE9]'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        }
      />
      <Divider />

      {tab === 'sessions' && <Sessions />}
      {tab === 'blockchain' && <BlockchainLedger />}
      {tab === 'analyze' && <FileAnalyzer />}
      {tab === 'speakers' && <SpeakerEnroll />}
    </article>
  )
}

/* ------------------------------ Sessions tab ------------------------------- */

function Sessions() {
  const [sessions, setSessions] = useState<any[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [windows, setWindows] = useState<any[]>([])

  useEffect(() => {
    fetch(`${apiBase()}/api/sessions`)
      .then((r) => r.json())
      .then((xs) => setSessions(Array.isArray(xs) ? xs : []))
      .catch(() => setSessions([]))
  }, [])

  useEffect(() => {
    if (!selected) return setWindows([])
    fetch(`${apiBase()}/api/sessions/${selected}/windows`)
      .then((r) => r.json())
      .then((xs) => setWindows(Array.isArray(xs) ? xs : []))
      .catch(() => setWindows([]))
  }, [selected])

  return (
    <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
      <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
        {sessions.length === 0 && (
          <p className="text-[13.5px] text-zinc-500">No sessions recorded yet — run a live monitor session first.</p>
        )}
        {sessions.map((s) => (
          <SessionCard key={s.id} s={s} active={selected === s.id} onClick={() => setSelected(s.id)} />
        ))}
      </div>

      <div>
        {selected ? (
          <div className="card p-6">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <h3 className="font-serif text-[20px] font-bold tracking-tight text-zinc-900">Window timeline</h3>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[12px] text-zinc-500">{selected}</span>
                <a
                  href={`${apiBase()}/api/report/${selected}`}
                  download
                  className={btn('btn-primary')}
                >
                  Download report
                </a>
              </div>
            </div>
            <div className="mt-3">
              <Sparkline values={windows.map((w) => w.synthetic_score)} height={64} />
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-[12.5px]">
                <thead>
                  <tr className="border-b border-[#E4E4E7] text-[11px] uppercase tracking-wide text-zinc-500">
                    <th className="py-2 pr-3 font-semibold">t (ms)</th>
                    <th className="py-2 pr-3 font-semibold">Score</th>
                    <th className="py-2 pr-3 font-semibold">Model</th>
                    <th className="py-2 pr-3 font-semibold">XAI</th>
                    <th className="py-2 pr-3 font-semibold">Jitter %</th>
                    <th className="py-2 pr-3 font-semibold">Shimmer %</th>
                    <th className="py-2 pr-3 font-semibold">φ cont</th>
                    <th className="py-2 font-semibold">Verdict</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {windows
                    .slice(-100)
                    .reverse()
                    .map((w) => (
                      <tr key={w.t_ms} className="border-b border-[#F1EEE9] last:border-0">
                        <td className="py-1.5 pr-3 text-zinc-500">{w.t_ms}</td>
                        <td className="py-1.5 pr-3 font-semibold" style={{ color: w.synthetic_score >= 0.85 ? '#DC2626' : w.synthetic_score >= 0.35 ? '#b45309' : '#3f6f4f' }}>
                          {w.synthetic_score?.toFixed(2)}
                        </td>
                        <td className="py-1.5 pr-3 text-zinc-800">{w.model_prob?.toFixed(2)}</td>
                        <td className="py-1.5 pr-3 text-zinc-800">{w.xai_risk?.toFixed(2)}</td>
                        <td className="py-1.5 pr-3 text-zinc-500">{w.jitter_pct?.toFixed(3)}</td>
                        <td className="py-1.5 pr-3 text-zinc-500">{w.shimmer_pct?.toFixed(3)}</td>
                        <td className="py-1.5 pr-3 text-zinc-500">{w.phase_continuity?.toFixed(2)}</td>
                        <td className="py-1.5 text-zinc-800">{w.verdict}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
              {windows.length === 0 && <p className="mt-2 text-[13px] text-zinc-500">No windows persisted for this session.</p>}
            </div>
          </div>
        ) : (
          <div className="card flex h-full items-center justify-center p-10 text-center">
            <p className="max-w-xs text-[13.5px] leading-relaxed text-zinc-500">
              Select a session on the left to reconstruct its full per-window analysis timeline.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

/* ------------------------------ Blockchain tab ----------------------------- */

function BlockchainLedger() {
  const [status, setStatus] = useState<any>(null)
  const [results, setResults] = useState<Record<string, any>>({})
  const [checking, setChecking] = useState<Record<string, boolean>>({})

  const load = () => {
    fetch(`${apiBase()}/api/blockchain`)
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => setStatus(null))
  }
  useEffect(load, [])

  const verify = async (block: any) => {
    const key = String(block.block_index)
    setChecking((c) => ({ ...c, [key]: true }))
    try {
      const r = await fetch(`${apiBase()}/api/blockchain/verify/call/${block.call_id}`)
      const j = await r.json()
      setResults((prev) => ({ ...prev, [key]: j }))
    } catch {
      setResults((prev) => ({ ...prev, [key]: { valid: false, error: 'verification failed' } }))
    } finally {
      setChecking((c) => ({ ...c, [key]: false }))
    }
  }

  return (
    <div className="space-y-5">
      <div className="card p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-serif text-[20px] font-bold tracking-tight text-zinc-900">Report blockchain</h3>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-zinc-500">
              Every forensic PDF is anchored via SHA-256 + proof-of-work to an append-only hash chain. Each block commits
              the report hash and a Merkle root of the session score timeline, linked to its predecessor — so any
              modification after the fact is cryptographically detectable.
            </p>
          </div>
          <span
            className="rounded-full px-3 py-1 text-[12px] font-bold"
            style={{
              background: status?.valid ? '#E7F1EA' : '#FDF2F2',
              color: status?.valid ? '#3f6f4f' : '#DC2626',
            }}
          >
            {status ? (status.valid ? `chain OK · height ${status.height}` : 'chain INVALID') : '…'}
          </span>
        </div>

        {status && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Height" value={status.height} />
            <Metric label="Difficulty" value={status.difficulty} />
            <Metric label="Genesis" value={status.genesis.slice(0, 12) + '…'} />
            <Metric label="Latest" value={status.latest.slice(0, 12) + '…'} />
          </div>
        )}
      </div>

      {status?.blocks?.length === 0 && (
        <p className="text-[13.5px] text-zinc-500">No reports anchored yet — download a forensic report to mint the genesis block.</p>
      )}

      {status?.blocks?.map((b: any) => {
        const key = String(b.block_index)
        const res = results[key]
        return (
          <div key={key} className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <span className="font-mono text-[12px] font-bold text-zinc-900">#{b.block_index}</span>
                <span className="font-mono text-[12.5px] text-zinc-600">{b.call_id}</span>
                <span className="rounded-full bg-[#F1EEE9] px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-zinc-500">
                  {b.report_id}
                </span>
              </div>
              {res ? (
                <span
                  className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-bold ${
                    res.valid ? 'bg-[#E7F1EA] text-[#3f6f4f]' : 'bg-[#FDF2F2] text-[#DC2626]'
                  }`}
                >
                  {res.valid ? '✓ VERIFIED' : '✗ INVALID'}
                </span>
              ) : (
                <button
                  onClick={() => verify(b)}
                  disabled={checking[key]}
                  className={btn(key === '0' ? 'btn-primary' : '')}
                >
                  {checking[key] ? 'Verifying…' : 'Verify'}
                </button>
              )}
            </div>

            <div className="mt-3.5 grid gap-x-6 gap-y-1.5 font-mono text-[11.5px] text-zinc-500 sm:grid-cols-2">
              <div>block hash&nbsp;&nbsp;{b.block_hash.slice(0, 20)}…</div>
              <div>prev hash&nbsp;&nbsp;{b.prev_hash.slice(0, 20)}…</div>
              <div>file sha256&nbsp;{b.file_sha256.slice(0, 20)}…</div>
              <div>merkle root&nbsp;{b.merkle_root.slice(0, 20)}…</div>
              <div>nonce&nbsp;&nbsp;{b.nonce}</div>
              <div>mined&nbsp;&nbsp;{new Date(b.timestamp).toLocaleString()}</div>
            </div>

            {res && (
              <div className="mt-3 space-y-1 border-t border-[#F1EEE9] pt-3 text-[12px]">
                {res.valid ? (
                  <p className="text-[#3f6f4f]">On-disk report hash matches the anchored hash; chain linkage intact.</p>
                ) : (
                  <>
                    <p className="text-[#DC2626]">
                      {(res.problems || [res.error]).join(' · ')}
                    </p>
                    {res.current_file_sha256 && (
                      <p className="font-mono text-zinc-500">
                        file now&nbsp;&nbsp;{res.current_file_sha256.slice(0, 24)}…<br />
                        anchored&nbsp;{res.anchored_file_sha256.slice(0, 24)}…
                      </p>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------- Analyze tab ------------------------------- */

function FileAnalyzer() {
  const [file, setFile] = useState<File | null>(null)
  const [role, setRole] = useState('adult')
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    if (!file) return
    setBusy(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await fetch(`${apiBase()}/api/analyze?role=${role}`, { method: 'POST', body: fd })
      setResult(await r.json())
    } catch {
      setResult({ error: 'Analysis failed — is the backend reachable?' })
    } finally {
      setBusy(false)
    }
  }

  const scores = useMemo(() => (result?.windows || []).map((w: any) => w.synthetic_score), [result])

  return (
    <div className="space-y-5">
      <div className="card p-6">
        <h3 className="font-serif text-[20px] font-bold tracking-tight text-zinc-900">Analyze a recording</h3>
        <p className="mt-1 max-w-xl text-[13.5px] leading-relaxed text-zinc-500">
          Upload a call recording (wav, mp3, flac). VoiceShield resamples to 16 kHz, slides a 300 ms window across the
          file, and returns the full per-window XAI breakdown.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept="audio/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="max-w-xs text-[13px] text-zinc-600 file:mr-3 file:rounded-full file:border-0 file:bg-[#F1EEE9] file:px-4 file:py-1.5 file:text-[12.5px] file:font-semibold file:text-zinc-900 hover:file:bg-[#E4E4E7]"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="rounded-full border border-[#E4E4E7] bg-white px-3.5 py-1.5 text-[13px] font-medium text-zinc-800 outline-none"
          >
            <option value="adult">adult</option>
            <option value="child">child</option>
          </select>
          <button onClick={run} disabled={!file || busy} className={btn('btn-primary')}>
            {busy ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>
      </div>

      {result &&
        (result.error ? (
          <p className="text-[13.5px]" style={{ color: '#DC2626' }}>
            {result.error}
          </p>
        ) : (
          <div className="card p-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <Metric label="Peak score" value={`${(result.peak_score * 100).toFixed(0)}%`} />
              <Metric label="Risk band" value={result.risk_band} />
              <Metric label="Windows analyzed" value={result.windows_analyzed} />
            </div>
            {scores.length > 0 && (
              <div className="mt-4">
                <Sparkline values={scores} height={56} />
              </div>
            )}
            <p className="mt-3 text-[13.5px] leading-relaxed text-zinc-600">{result.recommendation}</p>
          </div>
        ))}
    </div>
  )
}

/* ------------------------------- Speakers tab ------------------------------- */

function SpeakerEnroll() {
  const [label, setLabel] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [msg, setMsg] = useState('')

  const enroll = async () => {
    if (!label || !file) return setMsg('Provide a label and a genuine voice sample.')
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${apiBase()}/api/speakers/register?label=${encodeURIComponent(label)}&language=en`, {
      method: 'POST',
      body: fd,
    })
    const j = await r.json()
    setMsg(j.ok ? `Enrolled \"${label}\" — cross-session consistency checks are now active for this voice.` : `Error: ${j.detail || 'failed'}`)
  }

  return (
    <div className="card p-6">
      <h3 className="font-serif text-[20px] font-bold tracking-tight text-zinc-900">Enroll a trusted speaker</h3>
      <p className="mt-1 max-w-xl text-[13.5px] leading-relaxed text-zinc-500">
        Upload about ten seconds of genuine speech per person. Live sessions tagged with this label are compared
        against the stored embedding (pgvector cosine similarity); a mismatch adds +0.10 to the fused risk score.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Speaker label"
          className="w-48 rounded-lg border border-[#E4E4E7] bg-white px-3 py-2 text-[13.5px] text-zinc-900 outline-none transition-colors placeholder:text-zinc-400 focus:border-[#2563EB]"
        />
        <input
          type="file"
          accept="audio/*"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="max-w-xs text-[13px] text-zinc-600 file:mr-3 file:rounded-full file:border-0 file:bg-[#F1EEE9] file:px-4 file:py-1.5 file:text-[12.5px] file:font-semibold file:text-zinc-900 hover:file:bg-[#E4E4E7]"
        />
        <button onClick={enroll} className={btn()}>
          Enroll
        </button>
      </div>
      {msg && <p className="mt-3 text-[13.5px] text-zinc-600">{msg}</p>}
    </div>
  )
}

function Metric({ label, value, capitalize }: { label: string; value: any; capitalize?: boolean }) {
  return (
    <div className="rounded-lg bg-[#FAF8F5] px-4 py-3">
      <div className="text-[10.5px] font-bold uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={`mt-0.5 font-serif text-[22px] font-bold tracking-tight text-zinc-900 ${capitalize ? 'capitalize' : ''}`}>
        {value}
      </div>
    </div>
  )
}
