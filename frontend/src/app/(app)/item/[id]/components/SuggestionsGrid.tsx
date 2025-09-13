import Link from 'next/link'
import { SuggestionItem } from '../../../../../../lib/suggestions'

interface SuggestionsGridProps {
  suggestions: SuggestionItem[]
}

export default function SuggestionsGrid({ suggestions }: SuggestionsGridProps) {
  if (suggestions.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-gray-400 mb-4">
          <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">No matches available</h3>
        <p className="text-gray-600">
          Try uploading more items to get better suggestions.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      {suggestions.map((suggestion) => (
        <Link
          key={suggestion.garment_id}
          href={`/item/${suggestion.garment_id}`}
          className="group"
        >
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow">
            {/* Image */}
            <div className="aspect-square bg-gray-100 relative">
              <img
                src={suggestion.image_url}
                alt="Suggested outfit match"
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
              />
              
              {/* Score overlay */}
              <div className="absolute top-2 right-2">
                <div className="bg-black bg-opacity-75 text-white text-xs font-medium px-2 py-1 rounded">
                  {Math.round(suggestion.score * 100)}%
                </div>
              </div>
            </div>

            {/* Card content */}
            <div className="p-4">
              {/* Reasons */}
              <div className="space-y-1">
                {suggestion.reasons.map((reason: string, index: number) => (
                  <div key={index} className="flex items-start text-sm text-gray-600">
                    <span className="text-blue-500 mr-2">•</span>
                    <span className="capitalize">{reason}</span>
                  </div>
                ))}
              </div>
              
              {/* Match strength indicator */}
              <div className="mt-3 pt-3 border-t border-gray-100">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-500">Match strength</span>
                  <div className="flex items-center space-x-1">
                    {[1, 2, 3, 4, 5].map((level) => (
                      <div
                        key={level}
                        className={`w-2 h-2 rounded-full ${
                          level <= Math.round(suggestion.score * 5)
                            ? 'bg-blue-500'
                            : 'bg-gray-200'
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Link>
      ))}
    </div>
  )
}
