import type { ReactNode } from 'react'

type HeadingLevel = 'h1' | 'h2' | 'h3'

interface SectionHeadingProps {
  children: ReactNode
  eyebrow?: ReactNode
  description?: ReactNode
  as?: HeadingLevel
  align?: 'left' | 'center'
  className?: string
}

export default function SectionHeading({
  children,
  eyebrow,
  description,
  as: Heading = 'h2',
  align = 'left',
  className = '',
}: SectionHeadingProps) {
  return (
    <div
      className={`vf-section-heading vf-section-heading--${align} ${className}`.trim()}
    >
      {eyebrow && <p className="vf-section-heading__eyebrow">{eyebrow}</p>}
      <Heading
        className={`vf-section-heading__title vf-section-heading__title--${Heading}`}
      >
        {children}
      </Heading>
      <div className="vf-section-heading__ornament" aria-hidden="true">
        <span />
        <svg viewBox="0 0 24 14" fill="none" focusable="false">
          <path d="M12 1.5v11M7.75 7h8.5" />
          <path d="M9.25 4.25 12 7l2.75-2.75M9.25 9.75 12 7l2.75 2.75" />
        </svg>
        <span />
      </div>
      {description && (
        <p className="vf-section-heading__description">{description}</p>
      )}
    </div>
  )
}
