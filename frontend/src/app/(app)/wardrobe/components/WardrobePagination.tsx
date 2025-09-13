'use client'

import { useRouter, useSearchParams } from 'next/navigation'

interface WardrobePaginationProps {
  total: number
  page: number
  pageSize: number
}

export default function WardrobePagination({ total, page, pageSize }: WardrobePaginationProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  
  const totalPages = Math.ceil(total / pageSize)
  const hasNextPage = page < totalPages
  const hasPrevPage = page > 1

  const goToPage = (newPage: number) => {
    const params = new URLSearchParams(searchParams.toString())
    
    if (newPage <= 1) {
      params.delete('page')
    } else {
      params.set('page', newPage.toString())
    }
    
    const queryString = params.toString()
    const url = queryString ? `/wardrobe?${queryString}` : '/wardrobe'
    router.push(url)
  }

  // Don't show pagination if there's only one page
  if (totalPages <= 1) {
    return null
  }

  const getPageNumbers = () => {
    const pages = []
    const maxVisible = 5
    
    if (totalPages <= maxVisible) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Show current page with context
      const start = Math.max(1, page - 2)
      const end = Math.min(totalPages, page + 2)
      
      // Always include first page
      if (start > 1) {
        pages.push(1)
        if (start > 2) pages.push('...')
      }
      
      // Add pages around current
      for (let i = start; i <= end; i++) {
        pages.push(i)
      }
      
      // Always include last page
      if (end < totalPages) {
        if (end < totalPages - 1) pages.push('...')
        pages.push(totalPages)
      }
    }
    
    return pages
  }

  return (
    <div className="flex items-center justify-between">
      <div className="flex-1 flex justify-between sm:hidden">
        {/* Mobile pagination - simple prev/next */}
        <button
          onClick={() => goToPage(page - 1)}
          disabled={!hasPrevPage}
          className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <button
          onClick={() => goToPage(page + 1)}
          disabled={!hasNextPage}
          className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
      
      <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-gray-700">
            Showing{' '}
            <span className="font-medium">{((page - 1) * pageSize) + 1}</span>
            {' '}to{' '}
            <span className="font-medium">
              {Math.min(page * pageSize, total)}
            </span>
            {' '}of{' '}
            <span className="font-medium">{total}</span>
            {' '}results
          </p>
        </div>
        
        <div>
          <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
            {/* Previous button */}
            <button
              onClick={() => goToPage(page - 1)}
              disabled={!hasPrevPage}
              className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="sr-only">Previous</span>
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            </button>
            
            {/* Page numbers */}
            {getPageNumbers().map((pageNum, index) => (
              pageNum === '...' ? (
                <span
                  key={`ellipsis-${index}`}
                  className="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700"
                >
                  ...
                </span>
              ) : (
                <button
                  key={pageNum}
                  onClick={() => goToPage(pageNum as number)}
                  className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                    pageNum === page
                      ? 'z-10 bg-blue-50 border-blue-500 text-blue-600'
                      : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  {pageNum}
                </button>
              )
            ))}
            
            {/* Next button */}
            <button
              onClick={() => goToPage(page + 1)}
              disabled={!hasNextPage}
              className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="sr-only">Next</span>
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            </button>
          </nav>
        </div>
      </div>
    </div>
  )
}
