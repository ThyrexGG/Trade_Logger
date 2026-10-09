import type { JournalLink } from '../../types/operations'
import { CloseIcon, ExternalIcon, LinkIcon } from '../../lib/icons'
import { resolveChartImage } from '../../lib/tradingview'
import { ChartSnapshot } from './ChartSnapshot'

/**
 * Web links on a trade or a note: a TradingView idea or chart, a news
 * article, a video. Stored server-side in `journal_links` (http/https only,
 * at most MAX_LINKS). `JournalLinkChips` shows them; `JournalLinksEditor`
 * edits a list of drafts that `cleanLinks` turns into what the API takes.
 */

export const MAX_LINKS = 10

export interface LinkDraft {
  url: string
  label: string
}

const SITES: [RegExp, string][] = [
  [/(^|\.)tradingview\.com$/, 'TradingView'],
  [/(^|\.)forexfactory\.com$/, 'Forex Factory'],
  [/(^|\.)(youtube\.com|youtu\.be)$/, 'YouTube'],
  [/(^|\.)(x\.com|twitter\.com)$/, 'X'],
  [/(^|\.)investing\.com$/, 'Investing.com'],
  [/(^|\.)myfxbook\.com$/, 'Myfxbook'],
  [/(^|\.)docs\.google\.com$/, 'Google Docs'],
  [/(^|\.)notion\.(so|site)$/, 'Notion'],
]

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

export function isTradingView(url: string): boolean {
  return /(^|\.)tradingview\.com$/.test(host(url))
}

/** "TradingView", "Forex Factory"… or the bare domain. */
export function siteName(url: string): string {
  const h = host(url)
  for (const [re, name] of SITES) if (re.test(h)) return name
  return h || url
}

/** A pasted address as a full https URL, or null when it isn't a web address. */
export function normalizeUrl(raw: string): string | null {
  const t = raw.trim()
  if (!t) return null
  // "tradingview.com/x/abc" → "https://tradingview.com/x/abc"; anything with another scheme stays as typed (and fails below)
  const withScheme = /^[a-z][a-z0-9+.-]*:/i.test(t) ? t : /^[\w-]+(\.[\w-]+)+([/?#:]|$)/.test(t) ? `https://${t}` : t
  return /^https?:\/\/[^\s/$.?#]+\.[^\s]+$/i.test(withScheme) ? withScheme : null
}

export function toDrafts(links: JournalLink[] | null | undefined): LinkDraft[] {
  return (links ?? []).map((l) => ({ url: l.url, label: l.label ?? '' }))
}

/** Drafts → the API's link list. Empty rows are dropped; rows that aren't web addresses are counted, not sent. */
export function cleanLinks(drafts: LinkDraft[]): { links: JournalLink[]; invalid: number } {
  const links: JournalLink[] = []
  let invalid = 0
  for (const d of drafts) {
    if (!d.url.trim()) continue
    const url = normalizeUrl(d.url)
    if (!url) {
      invalid++
      continue
    }
    links.push({ url, label: d.label.trim() || null })
  }
  return { links: links.slice(0, MAX_LINKS), invalid }
}

/** A stable comparison key (labels: null and '' are the same). */
export function linksKey(links: JournalLink[] | null | undefined): string {
  return JSON.stringify((links ?? []).map((l) => [l.url, l.label || '']))
}

function SiteMark({ url }: { url: string }) {
  if (isTradingView(url)) {
    return (
      <span className="rounded-[3px] bg-[var(--tl-text-primary)] px-[3px] font-mono text-[9px] font-semibold leading-[13px] text-[var(--tl-background)]" aria-hidden="true">
        TV
      </span>
    )
  }
  return <LinkIcon width={13} height={13} />
}

/** Saved links as small chips that open in a new tab. */
export function JournalLinkChips({ links, className = '' }: { links: JournalLink[] | null | undefined; className?: string }) {
  if (!links?.length) return null
  return (
    <ul className={`flex flex-wrap gap-1.5 ${className}`} aria-label="Links">
      {links.map((l, i) => (
        <li key={`${l.url}-${i}`} className="min-w-0">
          <a
            href={l.url}
            target="_blank"
            rel="noopener noreferrer"
            title={l.url}
            className="inline-flex max-w-[18rem] items-center gap-1.5 rounded-[var(--tl-radius)] border border-border-subtle bg-surface-elevated px-2 py-1 text-[11.5px] text-secondary transition-colors hover:border-[var(--tl-accent-line)] hover:text-primary"
          >
            <SiteMark url={l.url} />
            <span className="truncate">{l.label || siteName(l.url)}</span>
            <ExternalIcon width={11} height={11} className="shrink-0 opacity-60" />
          </a>
        </li>
      ))}
    </ul>
  )
}

/**
 * Pictures for the saved links that ARE pictures: a TradingView snapshot link
 * (tradingview.com/x/...) or a direct image URL shows inline, the same way a
 * trade's chart link does. A TradingView *chart* link (tradingview.com/chart/...)
 * is a live page that needs a login, so it can't become an image: say how to get one.
 */
export function LinkPreviews({ links, className = '' }: { links: JournalLink[] | null | undefined; className?: string }) {
  const all = links ?? []
  const shots = all.filter((l) => resolveChartImage(l.url))
  const chartOnly = shots.length === 0 && all.some((l) => /tradingview\.com\/chart\//i.test(l.url))
  if (!shots.length && !chartOnly) return null
  return (
    <div className={`space-y-2 ${className}`}>
      {shots.map((l, i) => (
        <ChartSnapshot key={`${l.url}-${i}`} url={l.url} large />
      ))}
      {chartOnly ? (
        <p className="text-[11px] text-muted">
          A TradingView chart link can't show a picture here. On TradingView use the camera icon, choose "Copy link to the image", and add that link
          (it looks like tradingview.com/x/…), or paste a screenshot into the image box.
        </p>
      ) : null}
    </div>
  )
}

/**
 * Edit a list of links. The first row's placeholder invites a TradingView
 * link (the common case); every valid row gets an "open" button so links
 * stay clickable while editing.
 */
export function JournalLinksEditor({
  value,
  onChange,
  idPrefix,
}: {
  value: LinkDraft[]
  onChange: (next: LinkDraft[]) => void
  /** unique per editor, for the inputs' ids */
  idPrefix: string
}) {
  const rows = value.length ? value : [{ url: '', label: '' }]
  const set = (i: number, patch: Partial<LinkDraft>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const remove = (i: number) => onChange(rows.filter((_, j) => j !== i))

  return (
    <div className="space-y-2">
      {rows.map((r, i) => {
        const url = normalizeUrl(r.url)
        const bad = Boolean(r.url.trim()) && !url
        return (
          <div key={i}>
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor={`${idPrefix}-url-${i}`} className="sr-only">
                Link address
              </label>
              <input
                id={`${idPrefix}-url-${i}`}
                type="url"
                inputMode="url"
                value={r.url}
                onChange={(e) => set(i, { url: e.target.value })}
                onBlur={() => url && url !== r.url && set(i, { url })}
                placeholder={i === 0 ? 'TradingView link — https://www.tradingview.com/…' : 'Another link — article, video, idea…'}
                maxLength={2048}
                aria-invalid={bad || undefined}
                className="tl-input min-w-0 flex-[3_1_14rem]"
              />
              <label htmlFor={`${idPrefix}-label-${i}`} className="sr-only">
                Link name
              </label>
              <input
                id={`${idPrefix}-label-${i}`}
                value={r.label}
                onChange={(e) => set(i, { label: e.target.value })}
                placeholder={url ? siteName(url) : 'Name (optional)'}
                maxLength={80}
                className="tl-input min-w-0 flex-[1_1_8rem]"
              />
              <span className="flex items-center gap-1">
                {url ? (
                  <a href={url} target="_blank" rel="noopener noreferrer" className="tl-btn tl-btn--ghost tl-btn--sm" aria-label="Open link in a new tab" title="Open">
                    <ExternalIcon width={14} height={14} />
                  </a>
                ) : null}
                {rows.length > 1 || r.url || r.label ? (
                  <button type="button" onClick={() => remove(i)} className="tl-btn tl-btn--ghost tl-btn--sm" aria-label="Remove link" title="Remove">
                    <CloseIcon width={14} height={14} />
                  </button>
                ) : null}
              </span>
            </div>
            {bad ? (
              <p className="mt-1 text-[11px] text-warning" role="alert">
                That doesn&rsquo;t look like a web address — copy the full link (it starts with https://).
              </p>
            ) : null}
          </div>
        )
      })}
      {rows.length < MAX_LINKS ? (
        <button type="button" onClick={() => onChange([...rows, { url: '', label: '' }])} className="tl-btn tl-btn--ghost tl-btn--sm">
          + Add another link
        </button>
      ) : (
        <p className="text-[11px] text-muted">That&rsquo;s the maximum of {MAX_LINKS} links.</p>
      )}
    </div>
  )
}
