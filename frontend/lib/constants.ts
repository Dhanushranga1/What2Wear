/**
 * Constants for color bins and UI styling
 */

// Fixed color bins (must match backend palette.py)
export const COLOR_BINS = [
  'red', 'orange', 'yellow', 'green', 'teal', 
  'blue', 'purple', 'pink', 'brown', 'neutral'
] as const

export type ColorBin = typeof COLOR_BINS[number]

// Color mapping for UI display (neutral-ish colors for MVP)
export const BIN_COLORS: Record<string, string> = {
  red: '#EF4444',
  orange: '#F59E0B', 
  yellow: '#FACC15',
  green: '#22C55E',
  teal: '#14B8A6',
  blue: '#3B82F6',
  purple: '#A855F7',
  pink: '#EC4899',
  brown: '#92400E',
  neutral: '#9CA3AF'
}

// Category display names
export const CATEGORY_LABELS: Record<string, string> = {
  top: 'Top',
  bottom: 'Bottom',
  one_piece: 'One Piece'
}

// Pagination defaults
export const PAGE_SIZE_DEFAULT = 24
