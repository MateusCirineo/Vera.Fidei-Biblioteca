import type { HTMLAttributes, ReactNode } from 'react'

interface SurfaceCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  tone?: 'default' | 'gold' | 'wine' | 'transparent'
  interactive?: boolean
}

export default function SurfaceCard({
  children,
  tone = 'default',
  interactive = false,
  className = '',
  ...props
}: SurfaceCardProps) {
  return (
    <div
      className={`vf-surface-card vf-surface-card--${tone}${interactive ? ' vf-surface-card--interactive' : ''} ${className}`.trim()}
      {...props}
    >
      {children}
    </div>
  )
}
