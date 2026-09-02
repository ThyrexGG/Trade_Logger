import type { ReactNode } from 'react'

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
          {description ? (
            <p className="mt-1 max-w-2xl text-sm text-secondary">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      {children}
    </div>
  )
}
