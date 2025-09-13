import { notFound } from 'next/navigation'
import { fetchGarment, signSingleImageUrl } from '../../../../../lib/wardrobe'
import { fetchSuggestions } from '../../../../../lib/suggestions'
import { CATEGORY_LABELS } from '../../../../../lib/constants'
import Link from 'next/link'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import SuggestionsGrid from './components/SuggestionsGrid'

interface ItemPageProps {
  params: Promise<{ id: string }>
}

export default async function ItemPage({ params }: ItemPageProps) {
  const { id } = await params
  
  // Fetch garment data
  const garment = await fetchGarment(id)
  
  if (!garment) {
    notFound()
  }

  // Generate signed URL for the image
  const signedUrl = await signSingleImageUrl(garment.image_path)

  // Fetch suggestions (only for top/bottom items)
  const suggestionsData = garment.category !== 'one_piece' 
    ? await fetchSuggestions(id, 10)
    : null

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back button */}
        <div className="mb-6">
          <Link 
            href="/wardrobe"
            className="inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeftIcon className="h-5 w-5 mr-2" />
            Back to Wardrobe
          </Link>
        </div>

        <div className="bg-white shadow-lg rounded-lg overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Image Section */}
            <div className="aspect-square bg-gray-100 relative">
              {signedUrl ? (
                <img
                  src={signedUrl}
                  alt={`${garment.category} ${garment.subtype || ''}`}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <div className="text-center text-gray-500">
                    <svg className="mx-auto h-12 w-12 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p>Image not available</p>
                  </div>
                </div>
              )}
            </div>

            {/* Details Section */}
            <div className="p-6">
              <div className="mb-6">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                  {CATEGORY_LABELS[garment.category] || garment.category}
                </h1>
                {garment.subtype && (
                  <p className="text-xl text-gray-600">{garment.subtype}</p>
                )}
              </div>

              {/* Color Bins */}
              {garment.color_bins && garment.color_bins.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Colors</h3>
                  <div className="flex flex-wrap gap-3">
                    {garment.color_bins.map((color) => {
                      // Map colors to Tailwind classes
                      const colorMap: Record<string, string> = {
                        red: 'bg-red-500',
                        orange: 'bg-orange-500',
                        yellow: 'bg-yellow-400',
                        green: 'bg-green-500',
                        teal: 'bg-teal-500',
                        blue: 'bg-blue-500',
                        purple: 'bg-purple-500',
                        pink: 'bg-pink-500',
                        brown: 'bg-amber-800',
                        neutral: 'bg-gray-400'
                      }
                      const colorClass = colorMap[color] || 'bg-gray-400'
                      
                      return (
                        <div key={color} className="flex items-center space-x-2">
                          <div
                            className={`w-6 h-6 rounded-full border-2 border-gray-300 ${colorClass}`}
                            title={color}
                          />
                          <span className="text-sm text-gray-700 capitalize">{color}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Meta Tags */}
              {garment.meta_tags && garment.meta_tags.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Tags</h3>
                  <div className="flex flex-wrap gap-2">
                    {garment.meta_tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Metadata */}
              <div className="pt-6 border-t border-gray-200">
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Category</dt>
                    <dd className="mt-1 text-sm text-gray-900 capitalize">{garment.category}</dd>
                  </div>
                  {garment.subtype && (
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Subtype</dt>
                      <dd className="mt-1 text-sm text-gray-900">{garment.subtype}</dd>
                    </div>
                  )}
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Added</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      {new Date(garment.created_at).toLocaleDateString()}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Item ID</dt>
                    <dd className="mt-1 text-sm text-gray-900 font-mono">{garment.id}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
        </div>

        {/* Suggestions Section */}
        {suggestionsData && (
          <div className="mt-8 bg-white shadow-lg rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">
                Suggested Matches
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                {garment.category === 'top' ? 'Bottoms' : 'Tops'} that pair well with this item
              </p>
            </div>
            <div className="p-6">
              <SuggestionsGrid suggestions={suggestionsData.suggestions} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
