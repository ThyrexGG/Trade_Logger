import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { guideForPath } from '../../lib/pageGuides'
import { PageGuide } from '../shared/PageGuide'

interface PageContainerProps {
  title: string
  description?: ReactNode
  /** Right-aligned header slot (actions, status). */
  actions?: ReactNode
  /**
   * 'full' (default) uses all available width for dense terminal layouts.
   * 'standard' constrains reading-oriented pages.
   */
  width?: 'full' | 'standard'
  children: ReactNode
}

/** Consistent page scaffold: header + optional description + content area. */
export function PageContainer({
  title,
  description,
  actions,
  width = 'full',
  children,
}: PageContainerProps) {
  // A beginner guide for this route (see lib/pageGuides) replaces the terse
  // technical one-liner under the title.
  const { pathname } = useLocation()
  const guide = guideForPath(pathname)
  return (
    <div
      className={
        width === 'standard'
          ? 'mx-auto w-full max-w-3xl px-4 py-6 sm:px-6'
          : 'w-full px-4 py-6 sm:px-6'
      }
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-border-subtle pb-4">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-primary">{title}</h1>
          {description && !guide ? (
            <p className="mt-1 max-w-2xl text-sm text-secondary">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="w-full min-w-0 sm:w-auto sm:shrink-0">{actions}</div> : null}
      </div>
      {guide ? (
        <PageGuide id={guide.id} title={guide.guide.title} steps={guide.guide.steps}>
          {guide.guide.body}
        </PageGuide>
      ) : null}
      {children}
    </div>
  )
}
