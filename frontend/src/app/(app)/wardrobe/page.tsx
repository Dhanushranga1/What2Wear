import { fetchGarments, signImageUrls } from '../../../../lib/wardrobe'
import { GarmentWithSignedUrl } from '../../../../types/garments'
import WardrobeFilters from './components/WardrobeFilters'
import WardrobeGrid from './components/WardrobeGrid'
import WardrobePagination from './components/WardrobePagination'
import Link from 'next/link'

type SearchParams = {
  category?: string
  color?: string
  tag?: string
  page?: string
}

export default async function WardrobePage({ 
  searchParams 
}: { 
  searchParams: Promise<SearchParams>
}) {
  // Parse search parameters (await required in Next.js 15+)
  const params = await searchParams
  const category = params.category as 'top' | 'bottom' | 'one_piece' | undefined
  const color = params.color
  const tag = params.tag
  const page = params.page ? Number(params.page) : 1

  try {
    // Fetch garments with filters
    const { items, total, page: currentPage, pageSize } = await fetchGarments({
      category,
      color,
      tag,
      page
    })

    // Batch sign image URLs
    const paths = items.map(garment => garment.image_path)
    const signed = await signImageUrls(paths)
    const urlByPath = new Map(signed.map(s => [s.path, s.url]))

    // Combine garments with signed URLs
    const garmentsWithUrls: GarmentWithSignedUrl[] = items.map(garment => ({
      ...garment,
      signedUrl: urlByPath.get(garment.image_path) || null
    }))

    // Show empty state if no garments
    if (total === 0 && !category && !color && !tag) {
      return (
        <div className="bg-white shadow rounded-lg p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Your Wardrobe</h1>
          <div className="text-center py-12">
            <div className="text-gray-500 mb-4">
              <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4V2a1 1 0 011-1h8a1 1 0 011 1v2h4a1 1 0 011 1v2a1 1 0 01-1 1h-1v12a2 2 0 01-2 2H6a2 2 0 01-2-2V8H3a1 1 0 01-1-1V5a1 1 0 011-1h4z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No items yet</h3>
            <p className="text-gray-600 mb-4">
              Upload your first garment to start building your wardrobe.
            </p>
            <Link 
              href="/upload" 
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
            >
              Upload your first garment
            </Link>
          </div>
        </div>
      )
    }

    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Your Wardrobe</h1>
        
        <div className="space-y-6">
          {/* Filters */}
          <WardrobeFilters 
            current={{ category, color, tag }} 
          />

          {/* Results summary */}
          <div className="text-sm text-gray-600">
            {total === 0 ? (
              <p>No items match your filters.</p>
            ) : (
              <p>
                Showing {((currentPage - 1) * pageSize) + 1}-{Math.min(currentPage * pageSize, total)} of {total} items
              </p>
            )}
          </div>

          {/* Grid */}
          {garmentsWithUrls.length > 0 ? (
            <WardrobeGrid items={garmentsWithUrls} />
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500">No items match your current filters.</p>
              <Link 
                href="/wardrobe" 
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                Clear filters
              </Link>
            </div>
          )}

          {/* Pagination */}
          {total > pageSize && (
            <WardrobePagination 
              total={total} 
              page={currentPage} 
              pageSize={pageSize} 
            />
          )}
        </div>
      </div>
    )

  } catch (error) {
    console.error('Error loading wardrobe:', error)
    
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Your Wardrobe</h1>
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="text-red-800">
              <p className="font-medium">Could not load wardrobe</p>
              <p className="text-sm mt-1">Please try refreshing the page. If the problem persists, check your connection.</p>
            </div>
          </div>
        </div>
      </div>
    )
  }
}
