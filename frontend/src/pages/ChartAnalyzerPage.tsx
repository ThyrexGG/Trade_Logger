import { useEffect, useRef, useState } from 'react'
import { PageContainer } from '../components/shell/PageContainer'
import { getAIStatus } from '../api/ai'
import { analyzeChartFile, analyzeChartUrl } from '../api/chartAnalysis'
import type { ChartAnalysisResponse } from '../types/chartAnalysis'

const ACCEPT = 'image/png,image/jpeg,image/webp'
const MAX_MB = 6
const TV_LINK_RE = /^https:\/\/(www\.)?tradingview\.com\/x\/[A-Za-z0-9]+\/?(\?.*)?$/i

type Mode = 'upload' | 'link'

function ratingTone(rating: number): string {
  if (rating >= 7) return 'text-positive border-positive/30 bg-positive/10'
  if (rating >= 4) return 'text-warning border-warning/30 bg-warning/10'
  return 'text-negative border-negative/30 bg-negative/10'
}

function Stat({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-elevated/40 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-0.5 font-mono text-sm tabular-nums text-primary">
        {value === null || value === undefined ? '—' : value}
      </p>
    </div>
  )
}

/**
 * Chart Analyzer (`/workspace/chart-analyzer`). Upload a chart screenshot — or
 * paste a tradingview.com/x/... share link — and Gemini vision reads what's
 * visibly plotted (entry / stop / target / R:R) plus gives an opinionated
 * setup-quality rating. Pure image-to-JSON extraction: nothing here is saved,
 * and it has no path to orders, positions, or any TradeLogger account data.
 */
export function ChartAnalyzerPage() {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [mode, setMode] = useState<Mode>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [link, setLink] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ChartAnalysisResponse | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const c = new AbortController()
    getAIStatus(c.signal)
      .then((s) => setConfigured(s.configured))
      .catch(() => setConfigured(null))
    return () => c.abort()
  }, [])

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  // Paste a screenshot (Ctrl+V) anywhere on this page — no click-to-focus
  // needed first, since the whole page has exactly one drop target.
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith('image/'))
      const f = item?.getAsFile()
      if (!f) return
      e.preventDefault()
      setMode('upload')
      pickFile(f)
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function pickFile(f: File | null | undefined) {
    setError(null)
    setResult(null)
    if (!f) return
    if (!f.type.startsWith('image/')) {
      setError('That file is not an image.')
      return
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`That image is ${(f.size / 1024 / 1024).toFixed(1)} MB — max ${MAX_MB} MB.`)
      return
    }
    setFile(f)
  }

  const disabled = configured === false
  const canAnalyze = !disabled && !busy && (mode === 'upload' ? !!file : TV_LINK_RE.test(link.trim()))

  async function analyze() {
    if (!canAnalyze) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const r = mode === 'upload' && file
        ? await analyzeChartFile(file)
        : await analyzeChartUrl(link.trim())
      if (r.ok) {
        setResult(r)
      } else {
        setError(r.error ?? 'Analysis failed.')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <PageContainer
      title="Chart Analyzer"
      description="Upload a chart screenshot or paste a TradingView share link — Gemini vision reads the visible entry, stop, target and R:R, and gives an opinionated setup rating. Nothing is saved; it never touches orders, positions or account data."
    >
      {disabled ? (
        <div className="mb-4 rounded-lg border border-warning/30 bg-warning/10 p-4 text-xs text-warning">
          The AI assistant isn't configured on this server — an operator needs to set{' '}
          <code>GEMINI_API_KEY</code> in the backend environment.
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* input card */}
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex rounded-xl border border-border p-1 text-xs">
            {(['upload', 'link'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m)
                  setError(null)
                  setResult(null)
                }}
                className={`flex-1 rounded-lg px-2 py-1.5 font-medium transition-colors ${
                  mode === m ? 'shadow' : 'text-muted'
                }`}
                style={
                  mode === m
                    ? { background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }
                    : undefined
                }
              >
                {m === 'upload' ? 'Upload screenshot' : 'TradingView link'}
              </button>
            ))}
          </div>

          {mode === 'upload' ? (
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                pickFile(e.dataTransfer.files?.[0])
              }}
              onClick={() => fileRef.current?.click()}
              className={`flex h-40 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-center transition-colors ${
                dragOver ? 'border-accent bg-accent/5' : 'border-border text-muted hover:border-accent/50'
              }`}
            >
              {previewUrl ? (
                <img src={previewUrl} alt="chart preview" className="max-h-36 rounded object-contain" />
              ) : (
                <>
                  <span className="text-sm text-secondary">Drop, paste (Ctrl+V), or click to browse</span>
                  <span className="text-[10px] text-muted">PNG / JPEG / WebP, max {MAX_MB} MB</span>
                </>
              )}
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={(e) => {
                  pickFile(e.target.files?.[0])
                  e.target.value = ''
                }}
              />
            </div>
          ) : (
            <div>
              <input
                type="url"
                value={link}
                onChange={(e) => {
                  setLink(e.target.value)
                  setError(null)
                  setResult(null)
                }}
                placeholder="https://www.tradingview.com/x/XXXXXXXX/"
                className="w-full rounded-xl border border-border bg-surface-elevated/60 px-3.5 py-2.5 text-sm text-primary outline-none focus:border-accent"
              />
              <p className="mt-1.5 text-[10px] text-muted">
                Use TradingView's camera/share icon on a chart to get this kind of link, then paste it here.
                Fetched server-side — the image itself, nothing else.
              </p>
            </div>
          )}

          <button
            type="button"
            onClick={analyze}
            disabled={!canAnalyze}
            className="mt-3 w-full rounded-xl px-3 py-2.5 text-sm font-semibold shadow-lg disabled:opacity-40"
            style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
          >
            {busy ? 'Analyzing…' : 'Analyze chart'}
          </button>

          {error ? <p className="mt-2 text-xs text-negative" role="alert">{error}</p> : null}
        </div>

        {/* results card */}
        <div className="rounded-xl border border-border bg-surface p-4">
          {!result ? (
            <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 text-center text-muted">
              <div className="flex h-11 w-11 items-center justify-center rounded-full border border-border-subtle bg-surface-elevated text-lg">
                ◎
              </div>
              <p className="text-sm">Results appear here once a chart is analyzed.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-primary">
                    {result.symbol ?? 'Unknown symbol'}
                  </span>
                  {result.timeframe ? (
                    <span className="rounded border border-border-subtle px-1.5 py-0.5 text-[10px] font-mono text-muted">
                      {result.timeframe}
                    </span>
                  ) : null}
                  {result.direction ? (
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                        result.direction === 'long'
                          ? 'border-positive/30 bg-positive/10 text-positive'
                          : 'border-negative/30 bg-negative/10 text-negative'
                      }`}
                    >
                      {result.direction}
                    </span>
                  ) : null}
                </div>
                {result.extraction_confidence ? (
                  <span className="text-[10px] uppercase tracking-wider text-muted">
                    {result.extraction_confidence} confidence
                  </span>
                ) : null}
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label="Entry" value={result.entry} />
                <Stat label="Stop loss" value={result.stop_loss} />
                <Stat label="Take profit" value={result.take_profit} />
                <Stat label="R:R" value={result.risk_reward !== null ? `${result.risk_reward}R` : null} />
              </div>

              {result.additional_targets.length > 0 ? (
                <p className="text-xs text-secondary">
                  Additional targets: {result.additional_targets.join(', ')}
                </p>
              ) : null}

              {result.setup_rating !== null ? (
                <div className="flex items-start gap-3 rounded-lg border border-border-subtle bg-surface-elevated/40 p-3">
                  <span
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-sm font-bold ${ratingTone(result.setup_rating)}`}
                  >
                    {result.setup_rating}
                  </span>
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted">Setup rating · AI opinion</p>
                    <p className="mt-0.5 text-xs text-secondary">{result.rating_reasoning ?? 'No reasoning given.'}</p>
                  </div>
                </div>
              ) : null}

              {result.pattern || result.confluences.length > 0 ? (
                <div className="text-xs text-secondary">
                  {result.pattern ? (
                    <p>
                      <span className="text-muted">Pattern: </span>
                      {result.pattern}
                    </p>
                  ) : null}
                  {result.confluences.length > 0 ? (
                    <ul className="mt-1 list-inside list-disc space-y-0.5">
                      {result.confluences.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}

              {result.caveats ? (
                <p className="text-[11px] text-muted">
                  <span className="uppercase tracking-wider">Caveats: </span>
                  {result.caveats}
                </p>
              ) : null}

              <p className="border-t border-border-subtle pt-2 text-[10px] text-muted">{result.disclaimer}</p>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  )
}
