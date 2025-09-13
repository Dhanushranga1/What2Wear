/**
 * Type definitions for garments and wardrobe functionality
 */
export type Garment = {
  id: string
  category: 'top' | 'bottom' | 'one_piece'
  subtype: string | null
  image_path: string
  image_url: string | null // optional last used signed url
  color_bins: string[]     // e.g., ['blue','neutral']
  meta_tags: string[]      // e.g., ['casual','summer']
  created_at: string
}

/**
 * Garment with signed URL for display
 */
export type GarmentWithSignedUrl = Garment & {
  signedUrl: string | null
}

/**
 * Filter options for wardrobe queries
 */
export type WardrobeFilters = {
  category?: 'top' | 'bottom' | 'one_piece'
  color?: string // one of fixed bins
  tag?: string
  page?: number
  pageSize?: number
}

/**
 * Paginated wardrobe response
 */
export type WardrobeResponse = {
  items: Garment[]
  total: number
  page: number
  pageSize: number
}
