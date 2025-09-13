export default function Loading() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back button skeleton */}
        <div className="mb-6">
          <div className="inline-flex items-center">
            <div className="w-5 h-5 mr-2 bg-gray-200 rounded animate-pulse"></div>
            <div className="w-32 h-5 bg-gray-200 rounded animate-pulse"></div>
          </div>
        </div>

        <div className="bg-white shadow-lg rounded-lg overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Image Section Skeleton */}
            <div className="aspect-square bg-gray-200 animate-pulse"></div>

            {/* Details Section Skeleton */}
            <div className="p-6">
              <div className="mb-6">
                <div className="w-48 h-8 bg-gray-200 rounded animate-pulse mb-2"></div>
                <div className="w-32 h-6 bg-gray-200 rounded animate-pulse"></div>
              </div>

              {/* Color Bins Skeleton */}
              <div className="mb-6">
                <div className="w-16 h-5 bg-gray-200 rounded animate-pulse mb-3"></div>
                <div className="flex flex-wrap gap-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center space-x-2">
                      <div className="w-6 h-6 bg-gray-200 rounded-full animate-pulse"></div>
                      <div className="w-12 h-4 bg-gray-200 rounded animate-pulse"></div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Tags Skeleton */}
              <div className="mb-6">
                <div className="w-12 h-5 bg-gray-200 rounded animate-pulse mb-3"></div>
                <div className="flex flex-wrap gap-2">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="w-16 h-8 bg-gray-200 rounded-full animate-pulse"></div>
                  ))}
                </div>
              </div>

              {/* Metadata Skeleton */}
              <div className="pt-6 border-t border-gray-200">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i}>
                      <div className="w-16 h-4 bg-gray-200 rounded animate-pulse mb-1"></div>
                      <div className="w-24 h-4 bg-gray-200 rounded animate-pulse"></div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
