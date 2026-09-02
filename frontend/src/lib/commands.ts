import type { IconComponent } from './icons'
import { ZONES } from './navigation'

/**
 * Declarative command list for the command palette. Derived from the product
 * IA — future stages push new commands here (or extend the type) without
 * touching the palette component.
 */
export interface Command {
  id: string
  label: string
  description: string
  route: string
  zone: string
  icon: IconComponent
  keywords: string
}

export const COMMANDS: Command[] = ZONES.flatMap((zone) => {
  const zoneCommand: Command = {
    id: `zone:${zone.id}`,
    label: zone.label,
    description: zone.tagline,
    route: zone.path,
    zone: zone.shortLabel,
    icon: zone.icon,
    keywords: `${zone.label} ${zone.shortLabel} zone overview`.toLowerCase(),
  }
  const itemCommands: Command[] = zone.items.map((item) => ({
    id: `nav:${item.id}`,
    label: item.label,
    description: item.description,
    route: item.path,
    zone: zone.shortLabel,
    icon: item.icon,
    keywords:
      `${item.label} ${item.description} ${zone.shortLabel} ${zone.label}`.toLowerCase(),
  }))
  return [zoneCommand, ...itemCommands]
})

/** Case-insensitive token-AND match over label + keywords. */
export function filterCommands(query: string): Command[] {
  const q = query.trim().toLowerCase()
  if (!q) return COMMANDS
  const tokens = q.split(/\s+/)
  return COMMANDS.filter((cmd) => {
    const haystack = `${cmd.label.toLowerCase()} ${cmd.keywords}`
    return tokens.every((token) => haystack.includes(token))
  })
}
