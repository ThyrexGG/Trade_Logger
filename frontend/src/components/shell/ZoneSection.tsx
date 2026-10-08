import type { Zone } from '../../lib/navigation'
import { NavigationItem } from './NavigationItem'

interface ZoneSectionProps {
  zone: Zone
  onNavigate?: () => void
}

/** A group in the sidebar (Today, Plan, Review, Learn, Settings): a quiet label over its pages. */
export function ZoneSection({ zone, onNavigate }: ZoneSectionProps) {
  return (
    <div className="px-3">
      <p className="px-2.5 pb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-muted">{zone.shortLabel}</p>
      <div className="flex flex-col gap-0.5">
        {zone.items.map((item) => (
          <NavigationItem key={item.id} item={item} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  )
}
