import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { guideForPath } from '../../lib/pageGuides'
import { findZoneByPath } from '../../lib/navigation'
import { PageGuide } from '../shared/PageGuide'

interface PageContainerProps {
  title: string
  description?: ReactNode
  /** Right-aligned header slot (actions, status). */
  actions?: ReactNode
  /**
   * 'full' (default) uses the content width up to a comfortable maximum.
   * 'standard' constrains reading-oriented pages.
   */
  width?: 'full' | 'standard'
  children: ReactNode
}

/**
 * Page scaffold: the group it belongs to (eyebrow), a real title, actions on
 * the right, then the beginner guide (lib/pageGuides — it replaces the old
 * technical one-liner when a page has one), then content. Content is capped
 * at a readable width instead of stretching edge to edge on wide monitors.
 */
export function PageContainer({ title, description, actions, width = 'full', children }: PageContainerProps) {
  const { pathname } = useLocation()
  const guide = guideForPath(pathname)
  const zone = findZoneByPath(pathname)

  return (
    <div className={width === 'standard' ? 'mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8' : 'mx-auto w-full max-w-[1320px] px-4 py-6 sm:px-6 sm:py-8'}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          {zone ? <p className="tl-eyebrow mb-1">{zone.shortLabel}</p> : null}
          <h1 className="tl-page-title">{title}</h1>
          {description && !guide ? <p className="mt-1.5 max-w-2xl text-sm text-secondary">{description}</p> : null}
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
