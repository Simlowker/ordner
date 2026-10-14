// Forked from deepseek-harness@d743267 packages/client/ui-brand-official/src/client/Brand.tsx (MIT, Copyright (c) 2026
// DeepSeek). Ordner: the whale and the DeepSeek wordmark are replaced by Ordner's own mark and name.
import type { CSSProperties } from 'react'

/** Ordner's Swiss red (the cockpit's --accent). */
const RED = '#D52B1E'

/**
 * Ordner's mark: a white Swiss cross on a red rounded square, the cockpit's `.mark` drawn in SVG.
 * @param props.size - requested square edge in pixels.
 * @param props.className - host class keeping the surrounding geometry.
 * @returns the mark svg, decorative.
 */
export function OrdnerMark({ size, className }: { size: number, className?: string | undefined }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="4" fill={RED} />
      <rect x="13" y="6" width="6" height="20" fill="#fff" />
      <rect x="6" y="13" width="20" height="6" fill="#fff" />
    </svg>
  )
}

const NAME: CSSProperties = {
  font: '700 16px/1 var(--dsh-font-family-text-default)',
  letterSpacing: '-0.02em',
  color: 'var(--dsw-alias-label-primary, #111113)',
}

/**
 * Ordner's name beside the sidebar mark.
 * @returns the product name.
 */
export function OrdnerName() {
  return <span style={NAME}>Ordner</span>
}
