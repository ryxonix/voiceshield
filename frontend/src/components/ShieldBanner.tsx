import { useEffect } from 'react'

export function ShieldBanner({ mitigation, onDismiss }: { mitigation?: any; onDismiss?: () => void }) {
  if (!mitigation) return null

  const { action, score, threshold, role, message } = mitigation
  const isChild = action === 'child_shield' || role === 'child'

  useEffect(() => {
    // web audio stack gates the mic; no additional browser-level mute required
  }, [])

  if (isChild) {
    return (
      <div className="child-shield fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/98 px-6 text-center" role="alert">
        <div className="max-w-lg">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-[#FCEEE7]">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#C2410C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3 2.5 8.5 12 18l9.5-4.5L12 3z" />
              <path d="M12 18v3M6 21h12" />
            </svg>
          </div>
          <div className="font-serif text-[22px] font-bold tracking-tight text-zinc-900 leading-tight">
            Call paused
          </div>
          <p className="mt-2 text-[14px] leading-relaxed text-zinc-600">
            {message || 'A potential AI-cloned voice was detected. A trusted guardian should verify the caller before continuing.'}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button
              onClick={onDismiss}
              className="rounded-full border border-zinc-900 bg-zinc-900 px-6 py-2 text-[13.5px] font-semibold text-white transition-colors hover:bg-zinc-700"
            >
              Dismiss
            </button>
          </div>
          <div className="mt-6 flex items-center justify-center gap-2.5 text-[12px] text-zinc-500">
            <span className="font-semibold text-zinc-700">{role}</span>
            <span className="text-zinc-300">· synthetic score</span>
            <span className="font-mono text-zinc-900">{(score * 100).toFixed(0)}%</span>
            <span className="text-zinc-300">threshold {(threshold * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>
    )
  }

  // adult → non-blocking inline risk banner
  return (
    <div
      className="risk-banner rounded-xl border border-zinc-900 bg-zinc-900/5 px-4 py-3 text-[13.5px] leading-relaxed shadow-sm"
      role="status"
    >
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#71717A" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5">
          <path d="M12 3 2.5 8.5 12 18l9.5-4.5L12 3z" />
          <path d="M12 18v3M6 21h12" />
        </svg>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium text-zinc-900">{message}</span>
          <span className="font-mono text-zinc-500">{(score * 100).toFixed(0)}% synthetic</span>
          <span className="text-zinc-400">· threshold {(threshold * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  )
}
