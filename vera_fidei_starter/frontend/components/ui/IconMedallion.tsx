import type { ReactNode } from 'react'

interface IconMedallionProps {
  children: ReactNode
  size?: 'sm' | 'md' | 'lg'
  tone?: 'gold' | 'wine'
  label?: string
  className?: string
}

export default function IconMedallion({
  children,
  size = 'md',
  tone = 'gold',
  label,
  className = '',
}: IconMedallionProps) {
  return (
    <span
      className={`vf-icon-medallion vf-icon-medallion--${size} vf-icon-medallion--${tone} ${className}`.trim()}
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
