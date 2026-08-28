import type { ReactNode } from 'react'

interface IconMedallionProps {
  children: ReactNode
  size?: 'sm' | 'compact' | 'md' | 'lg'
  tone?: 'gold' | 'wine'
  label?: string
  className?: string
  artwork?: boolean
}

export default function IconMedallion({
  children,
  size = 'md',
  tone = 'gold',
  label,
  className = '',
  artwork = false,
}: IconMedallionProps) {
  return (
    <span
      className={`vf-icon-medallion vf-icon-medallion--${size} vf-icon-medallion--${tone} ${artwork ? 'vf-icon-medallion--artwork' : ''} ${className}`.trim()}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <span className="vf-icon-medallion__glyph" aria-hidden="true">
        {children}
      </span>
    </span>
  )
}
