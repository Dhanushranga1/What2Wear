'use client'

import Link from 'next/link'
import { GarmentWithSignedUrl } from '../../../../../types/garments'
import { CATEGORY_LABELS } from '../../../../../lib/constants'

interface WardrobeGridProps {
  items: GarmentWithSignedUrl[]
}

function ColorDot({ color }: { color: string }) {
  // Use a CSS custom property to pass the color
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
    <div 
      className={`w-3 h-3 rounded-full border border-gray-200 ${colorClass}`}
      title={color.charAt(0).toUpperCase() + color.slice(1)}
    />
  )
}

function GarmentCard({ garment }: { garment: GarmentWithSignedUrl }) {
  const createdDate = new Date(garment.created_at).toLocaleDateString()

  return (
    <Link href={`/item/${garment.id}`} className="group">
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow">
        {/* Image */}
        <div className="aspect-square bg-gray-100 relative">
          {garment.signedUrl ? (
            <img
              src={garment.signedUrl}
              alt={`${garment.category} ${garment.subtype || ''}`.trim()}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}
          
          {/* Category chip overlay */}
          <div className="absolute top-2 left-2">
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-white/90 text-gray-800">
              {CATEGORY_LABELS[garment.category]}
            </span>
          </div>
        </div>

        {/* Content */}
        <div className="p-3">
          {/* Subtype */}
          {garment.subtype && (
            <h3 className="font-medium text-gray-900 text-sm mb-2 truncate">
              {garment.subtype}
            </h3>
          )}

          {/* Color bins */}
          {garment.color_bins.length > 0 && (
            <div className="flex items-center gap-1 mb-2">
              <span className="text-xs text-gray-600 mr-1">Colors:</span>
              {garment.color_bins.slice(0, 6).map((color, index) => (
                <ColorDot key={index} color={color} />
              ))}
              {garment.color_bins.length > 6 && (
                <span className="text-xs text-gray-500">+{garment.color_bins.length - 6}</span>
              )}
            </div>
          )}

          {/* Meta tags */}
          {garment.meta_tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {garment.meta_tags.slice(0, 3).map((tag, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800"
                >
                  {tag}
                </span>
              ))}
              {garment.meta_tags.length > 3 && (
                <span className="text-xs text-gray-500">+{garment.meta_tags.length - 3}</span>
              )}
            </div>
          )}

          {/* Created date */}
          <div className="text-xs text-gray-500">
            Added {createdDate}
          </div>
        </div>
      </div>
    </Link>
  )
}

export default function WardrobeGrid({ items }: WardrobeGridProps) {
  if (items.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-gray-400 mb-4">
          <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">No items found</h3>
        <p className="text-gray-600">Try adjusting your filters to see more results.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
      {items.map((garment) => (
        <GarmentCard key={garment.id} garment={garment} />
      ))}
    </div>
  )
}
