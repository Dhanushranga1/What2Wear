/**
 * Server-side utilities for wardrobe data fetching and signed URL generation
 */
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { WardrobeFilters, WardrobeResponse, Garment } from '../types/garments'
import { PAGE_SIZE_DEFAULT } from './constants'

/**
 * Create Supabase server client
 */
async function createSupabaseServerClient() {
  const cookieStore = await cookies()
  
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value
        },
      },
    }
  )
}

/**
 * Fetch garments with filters and pagination
 */
export async function fetchGarments(filters: WardrobeFilters = {}): Promise<WardrobeResponse> {
  const supabase = await createSupabaseServerClient()
  const pageSize = filters.pageSize ?? PAGE_SIZE_DEFAULT
  const page = Math.max(1, filters.page ?? 1)
  const from = (page - 1) * pageSize
  const to = from + pageSize - 1

  let query = supabase
    .from('garments')
    .select('id, category, subtype, image_path, image_url, color_bins, meta_tags, created_at', { count: 'exact' })
    .order('created_at', { ascending: false })
    .range(from, to)

  // Apply filters
  if (filters.category) {
    query = query.eq('category', filters.category)
  }
  if (filters.color) {
    query = query.contains('color_bins', [filters.color])
  }
  if (filters.tag) {
    query = query.contains('meta_tags', [filters.tag])
  }

  const { data, error, count } = await query

  if (error) {
    console.error('Error fetching garments:', error)
    throw new Error('Failed to fetch garments')
  }

  return {
    items: data ?? [],
    total: count ?? 0,
    page,
    pageSize
  }
}

/**
 * Batch generate signed URLs for image paths
 */
export async function signImageUrls(
  paths: string[], 
  expiresIn: number = 60 * 60 * 24 // 24 hours default
): Promise<Array<{ path: string; url: string | null }>> {
  if (paths.length === 0) {
    return []
  }

  const supabase = await createSupabaseServerClient()
  
  try {
    const { data, error } = await supabase.storage
      .from('wardrobe')
      .createSignedUrls(paths, expiresIn)

    if (error) {
      console.error('Error creating signed URLs:', error)
      // Return paths with null URLs as fallback
      return paths.map(path => ({ path, url: null }))
    }

    // Map results back to path-url pairs
    return paths.map((path, index) => ({
      path,
      url: data?.[index]?.signedUrl ?? null
    }))
  } catch (error) {
    console.error('Exception creating signed URLs:', error)
    // Return paths with null URLs as fallback
    return paths.map(path => ({ path, url: null }))
  }
}

/**
 * Fetch a single garment by ID
 */
export async function fetchGarment(id: string): Promise<Garment | null> {
  const supabase = await createSupabaseServerClient()

  const { data, error } = await supabase
    .from('garments')
    .select('id, category, subtype, image_path, image_url, color_bins, meta_tags, created_at')
    .eq('id', id)
    .single()

  if (error) {
    console.error('Error fetching garment:', error)
    return null
  }

  return data
}

/**
 * Generate a single signed URL for an image path
 */
export async function signSingleImageUrl(
  path: string,
  expiresIn: number = 60 * 60 * 24 // 24 hours default
): Promise<string | null> {
  const supabase = await createSupabaseServerClient()

  try {
    const { data, error } = await supabase.storage
      .from('wardrobe')
      .createSignedUrl(path, expiresIn)

    if (error) {
      console.error('Error creating signed URL:', error)
      return null
    }

    return data?.signedUrl ?? null
  } catch (error) {
    console.error('Exception creating signed URL:', error)
    return null
  }
}
