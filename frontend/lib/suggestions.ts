/**
 * Utilities for fetching outfit suggestions from the backend
 */
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export interface SuggestionItem {
  garment_id: string
  image_url: string
  score: number
  reasons: string[]
}

export interface SuggestionResponse {
  source_id: string
  suggestions: SuggestionItem[]
}

/**
 * Create Supabase server client to get access token
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
 * Fetch outfit suggestions from the backend
 */
export async function fetchSuggestions(
  garmentId: string,
  limit: number = 10
): Promise<SuggestionResponse | null> {
  try {
    const supabase = await createSupabaseServerClient()
    
    // Get the current session to extract the access token
    const { data: { session } } = await supabase.auth.getSession()
    
    if (!session?.access_token) {
      console.error('No access token available')
      return null
    }

    // Call our backend endpoint
    const response = await fetch(
      `http://localhost:8000/suggest/${garmentId}?limit=${limit}`,
      {
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      if (response.status === 404) {
        console.error('Garment not found or not owned')
        return null
      }
      console.error('Failed to fetch suggestions:', response.status)
      return null
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching suggestions:', error)
    return null
  }
}
