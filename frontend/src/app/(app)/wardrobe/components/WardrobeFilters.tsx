'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useState } from 'react'
import { COLOR_BINS, CATEGORY_LABELS } from '../../../../../lib/constants'

interface WardrobeFiltersProps {
  current: {
    category?: 'top' | 'bottom' | 'one_piece'
    color?: string
    tag?: string
  }
}

export default function WardrobeFilters({ current }: WardrobeFiltersProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [tagInput, setTagInput] = useState(current.tag || '')

  const updateFilter = (key: string, value: string | undefined) => {
    const params = new URLSearchParams(searchParams.toString())
    
    if (value && value !== '') {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    
    // Reset to page 1 when filters change
    params.delete('page')
    
    const queryString = params.toString()
    const url = queryString ? `/wardrobe?${queryString}` : '/wardrobe'
    router.push(url)
  }

  const clearAllFilters = () => {
    setTagInput('')
    router.push('/wardrobe')
  }

  const hasActiveFilters = current.category || current.color || current.tag

  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <div className="flex flex-wrap gap-4 items-end">
        {/* Category Filter */}
        <div className="min-w-[120px]">
          <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Category
          </label>
          <select
            id="category-filter"
            value={current.category || ''}
            onChange={(e) => updateFilter('category', e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
          >
            <option value="">All categories</option>
            <option value="top">{CATEGORY_LABELS.top}</option>
            <option value="bottom">{CATEGORY_LABELS.bottom}</option>
            <option value="one_piece">{CATEGORY_LABELS.one_piece}</option>
          </select>
        </div>

        {/* Color Filter */}
        <div className="min-w-[120px]">
          <label htmlFor="color-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Color
          </label>
          <select
            id="color-filter"
            value={current.color || ''}
            onChange={(e) => updateFilter('color', e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
          >
            <option value="">All colors</option>
            {COLOR_BINS.map(bin => (
              <option key={bin} value={bin}>
                {bin.charAt(0).toUpperCase() + bin.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Tag Filter */}
        <div className="min-w-[140px]">
          <label htmlFor="tag-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Tag
          </label>
          <div className="flex gap-2">
            <input
              id="tag-filter"
              type="text"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  updateFilter('tag', tagInput.trim())
                }
              }}
              placeholder="e.g., casual"
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
            />
            <button
              onClick={() => updateFilter('tag', tagInput.trim())}
              className="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              Apply
            </button>
          </div>
        </div>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <div>
            <button
              onClick={clearAllFilters}
              className="px-3 py-2 text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 text-sm"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-sm text-gray-600">Active filters:</span>
          {current.category && (
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              {CATEGORY_LABELS[current.category]}
              <button
                onClick={() => updateFilter('category', undefined)}
                className="ml-1 text-blue-600 hover:text-blue-800"
              >
                ×
              </button>
            </span>
          )}
          {current.color && (
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
              {current.color.charAt(0).toUpperCase() + current.color.slice(1)}
              <button
                onClick={() => updateFilter('color', undefined)}
                className="ml-1 text-green-600 hover:text-green-800"
              >
                ×
              </button>
            </span>
          )}
          {current.tag && (
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
              {current.tag}
              <button
                onClick={() => updateFilter('tag', undefined)}
                className="ml-1 text-purple-600 hover:text-purple-800"
              >
                ×
              </button>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
