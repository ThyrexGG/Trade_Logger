import { Fragment, type ReactNode } from 'react'

/**
 * Tiny, dependency-free Markdown renderer for assistant replies. Builds React
 * elements (never dangerouslySetInnerHTML). Supports fenced code, headings,
 * bullet / numbered lists, blockquotes, horizontal rules, paragraphs, and the
 * inline set: **bold**, *italic* / _italic_, `code`, [text](url).
 */
export function ChatMarkdown({ text }: { text: string }) {
  return <div className="tl-md space-y-2 text-sm leading-relaxed">{renderBlocks(text)}</div>
}

let keySeq = 0
const k = () => `md${keySeq++}`

function renderBlocks(src: string): ReactNode[] {
  const lines = src.replace(/\r\n/g, '\n').split('\n')
  const out: ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // blank
    if (!line.trim()) {
      i += 1
      continue
    }

    // fenced code
    const fence = line.match(/^```(\w*)\s*$/)
    if (fence) {
      const body: string[] = []
      i += 1
      while (i < lines.length && !/^```\s*$/.test(lines[i])) {
        body.push(lines[i])
        i += 1
      }
      i += 1 // closing fence
      out.push(
        <pre
          key={k()}
          className="overflow-x-auto rounded-md border border-border-subtle bg-background px-3 py-2 font-mono text-[12px] text-secondary"
        >
          <code>{body.join('\n')}</code>
        </pre>,
      )
      continue
    }

    // horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      out.push(<hr key={k()} className="border-border-subtle" />)
      i += 1
      continue
    }

    // heading
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      const level = h[1].length
      const cls =
        level <= 1
          ? 'text-base font-semibold text-primary'
          : level === 2
            ? 'text-sm font-semibold text-primary'
            : 'text-sm font-medium text-secondary'
      out.push(
        <p key={k()} className={`${cls} mt-1`}>
          {renderInline(h[2])}
        </p>,
      )
      i += 1
      continue
    }

    // blockquote
    if (/^>\s?/.test(line)) {
      const body: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        body.push(lines[i].replace(/^>\s?/, ''))
        i += 1
      }
      out.push(
        <blockquote
          key={k()}
          className="border-l-2 border-accent/40 pl-3 text-secondary italic"
        >
          {renderInline(body.join(' '))}
        </blockquote>,
      )
      continue
    }

    // list (unordered or ordered) — consecutive item lines
    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line)
      const items: string[] = []
      while (i < lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, ''))
        i += 1
      }
      const ListTag = ordered ? 'ol' : 'ul'
      out.push(
        <ListTag
          key={k()}
          className={`${ordered ? 'list-decimal' : 'list-disc'} space-y-0.5 pl-5 text-sm`}
        >
          {items.map((it) => (
            <li key={k()}>{renderInline(it)}</li>
          ))}
        </ListTag>,
      )
      continue
    }

    // paragraph — consecutive non-blank, non-special lines
    const para: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^```/.test(lines[i]) &&
      !/^(#{1,6}\s|>\s?|-{3,}\s*$|\*{3,}\s*$|_{3,}\s*$)/.test(lines[i]) &&
      !/^\s*([-*+]|\d+\.)\s+/.test(lines[i])
    ) {
      para.push(lines[i])
      i += 1
    }
    out.push(
      <p key={k()} className="text-sm">
        {renderInline(para.join(' '))}
      </p>,
    )
  }

  return out
}

/** Inline: `code` is extracted first so its contents are never re-parsed. */
function renderInline(text: string): ReactNode {
  const parts: ReactNode[] = []
  const re = /`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*\n]+)\*|_([^_\n]+)_|\[([^\]]+)\]\(([^)\s]+)\)/g
  let last = 0
  let m: RegExpExecArray | null

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<Fragment key={k()}>{text.slice(last, m.index)}</Fragment>)
    if (m[1] !== undefined) {
      parts.push(
        <code key={k()} className="rounded bg-surface-elevated px-1 py-0.5 font-mono text-[12px] text-primary">
          {m[1]}
        </code>,
      )
    } else if (m[2] !== undefined || m[3] !== undefined) {
      parts.push(
        <strong key={k()} className="font-semibold text-primary">
          {m[2] ?? m[3]}
        </strong>,
      )
    } else if (m[4] !== undefined || m[5] !== undefined) {
      parts.push(<em key={k()}>{m[4] ?? m[5]}</em>)
    } else if (m[6] !== undefined && m[7] !== undefined) {
      const href = m[7]
      const safe = /^(https?:|mailto:|\/)/.test(href)
      parts.push(
        safe ? (
          <a
            key={k()}
            href={href}
            target="_blank"
            rel="noreferrer noopener"
            className="text-accent underline underline-offset-2 hover:no-underline"
          >
            {m[6]}
          </a>
        ) : (
          <Fragment key={k()}>{m[6]}</Fragment>
        ),
      )
    }
    last = re.lastIndex
  }
  if (last < text.length) parts.push(<Fragment key={k()}>{text.slice(last)}</Fragment>)
  return parts
}
