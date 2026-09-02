import type { SVGProps } from 'react'

/**
 * Small hand-rolled icon set (no icon-library dependency). Each icon is a
 * 24x24 stroked glyph that inherits `currentColor`.
 */
type IconProps = SVGProps<SVGSVGElement>

function Base({ children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  )
}

export function CandlesIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M7 4v3m0 10v3M17 6v3m0 8v3" />
      <rect x="4" y="7" width="6" height="10" rx="1" />
      <rect x="14" y="9" width="6" height="8" rx="1" />
    </Base>
  )
}

export function ShieldIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
      <path d="M9 12l2 2 4-4" />
    </Base>
  )
}

export function LayersIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5M3 17l9 5 9-5" />
    </Base>
  )
}

export function BrainIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M9 4a3 3 0 00-3 3 3 3 0 00-1 5 3 3 0 001 5 3 3 0 003 3 3 3 0 003-1V4a3 3 0 00-3-1" />
      <path d="M12 5a3 3 0 013-1 3 3 0 013 3 3 3 0 011 5 3 3 0 01-1 5 3 3 0 01-3 3 3 3 0 01-3-1" />
    </Base>
  )
}

export function FlaskIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3" />
      <path d="M7 15h10" />
    </Base>
  )
}

export function ReplayIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M3 12a9 9 0 109-9" />
      <path d="M3 4v5h5" />
    </Base>
  )
}

export function GaugeIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M4 18a8 8 0 1116 0" />
      <path d="M12 18l4-5" />
    </Base>
  )
}

export function ChartIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M4 4v16h16" />
      <path d="M8 14l3-3 3 2 4-5" />
    </Base>
  )
}

export function ScaleIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M12 4v16M6 20h12" />
      <path d="M5 8h14M5 8l-2 5a3 3 0 006 0zM19 8l-2 5a3 3 0 006 0z" />
    </Base>
  )
}

export function BookIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M5 4h11a2 2 0 012 2v14H7a2 2 0 01-2-2V4z" />
      <path d="M5 16h13M9 8h6" />
    </Base>
  )
}

export function SearchIcon(props: IconProps) {
  return (
    <Base {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.5-4.5" />
    </Base>
  )
}

export function CpuIcon(props: IconProps) {
  return (
    <Base {...props}>
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" />
      <rect x="10" y="10" width="4" height="4" />
    </Base>
  )
}

export function MenuIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </Base>
  )
}

export function CloseIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Base>
  )
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M9 6l6 6-6 6" />
    </Base>
  )
}

export function EnterIcon(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M9 10l-4 4 4 4" />
      <path d="M5 14h11a4 4 0 004-4V6" />
    </Base>
  )
}

export type IconComponent = (props: IconProps) => React.ReactElement
