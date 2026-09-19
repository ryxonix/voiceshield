import { useCallback, useEffect, useState } from 'react'
import { Breadcrumbs, PageHeader, Divider, apiBase, btn } from '../components/ui'
import { useT } from '../i18n'

export default function Incidents() {
  const t = useT()
  const [incidents, setIncidents] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ackBusy, setAckBusy] = useState<Set<string>>(new Set())

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch(`${apiBase()}/api/incidents`)
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
      const xs = await r.json()
      setIncidents(Array.isArray(xs) ? xs : [])
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Failed to load incidents'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  const ack = async (id: string) => {
    setAckBusy((prev) => new Set(prev).add(id))
    try {
      const r = await fetch(`${apiBase()}/api/incidents/${id}/ack`, { method: 'POST' })
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
      setIncidents((prev) => prev.map((i) => (i.id === id ? { ...i, acknowledged: true } : i)))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Failed to acknowledge incident'))
    } finally {
      setAckBusy((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const severityLabel = (s: string) => {
    switch (s) {
      case 'critical':
        return t('sev.critical')
      case 'high':
        return t('sev.high')
      case 'medium':
        return t('sev.medium')
      default:
        return t('sev.low')
    }
  }

  const severityColor = (s: string) => {
    switch (s) {
      case 'critical':
        return '#DC2626'
      case 'high':
        return '#DC2626'
      case 'medium':
        return '#b45309'
      default:
        return '#3f6f4f'
    }
  }

  function created_at(ts: string | Date): string {
    const d = ts instanceof Date ? ts : new Date(ts)
    return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' })
  }

  const empty = incidents.length === 0

  return (
    <article className={empty ? '' : ''}>
      <Breadcrumbs trail={[t('Risk & incidents'), t('Incident log')]} />
      <PageHeader
        title={t('Incident log')}
        meta={t('Threshold crossings are recorded as incidents with severity, triggers and a forensic I4C report. Acknowledge incidents once they’ve been reviewed.')}
        actions={
          <button className={btn()} onClick={load} disabled={loading}>
            {loading ? t('Loading…') : t('Refresh')}
          </button>
        }
      />
      <Divider />

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
          {t('Error: {e}', { e: error })}
        </div>
      )}

      {empty ? (
        <div className="card p-10 text-center">
          <p className="text-[13.5px] text-zinc-500">
            {t('No incidents recorded yet. Run a live monitor session or upload a recording to see incidents here.')}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((inc) => (
            <article key={inc.id} className={`card p-5 ${inc.acknowledged ? 'opacity-60' : ''}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-[13px] text-zinc-500">{inc.id}</span>
                  <span className="rounded-full bg-[#FCEEE7] px-2 py-0.5 text-[11px] font-bold text-[#C2410C]">
                    {severityLabel(inc.severity)}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1.5 text-[12px] text-zinc-500">
                    <span className="font-semibold text-zinc-800">{severityLabel(inc.severity)}</span>
                    <span className="font-mono" style={{ color: severityColor(inc.severity) }}>
                      {(inc.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <a
                    className="rounded-full border border-[#E4E4E7] bg-white px-3 py-1 text-[12px] font-medium text-zinc-800 transition-colors hover:bg-[#F1EEE9]"
                    href={`${apiBase()}/api/incidents/${inc.id}/report`}
                  >
                    {t('I4C report')}
                  </a>
                  {inc.acknowledged ? (
                    <span className="text-[12px] font-medium text-zinc-500">{t('Acknowledged')}</span>
                  ) : (
                    <button
                      className="rounded-full border border-zinc-900 bg-zinc-900 px-3 py-1 text-[12px] font-medium text-white transition-colors hover:bg-zinc-700"
                      disabled={ackBusy.has(inc.id)}
                      onClick={() => ack(inc.id)}
                    >
                      {ackBusy.has(inc.id) ? t('Ack…') : t('Acknowledge')}
                    </button>
                  )}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-[11.5px] text-zinc-500">
                <span>{t('role {r}', { r: inc.role })}</span>
                <span>{t('lang {l}', { l: inc.language })}</span>
                <span>{created_at(inc.created_at)}</span>
                {inc.speaker_mismatch && <span className="font-semibold text-[#C2410C]">{t('speaker mismatch')}</span>}
                {inc.triggers?.length ? <span className="text-zinc-400">{t('triggers: {t}', { t: inc.triggers.join(', ') })}</span> : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </article>
  )
}
