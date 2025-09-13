export default function Loading() {
  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="mb-6">
        <div className="w-48 h-8 bg-gray-200 rounded animate-pulse"></div>
      </div>
      
      <div className="space-y-6">
        {/* Filters Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i}>
              <div className="w-16 h-4 bg-gray-200 rounded animate-pulse mb-2"></div>
              <div className="w-full h-10 bg-gray-200 rounded animate-pulse"></div>
            </div>
          ))}
        </div>

        {/* Results summary skeleton */}
        <div className="w-64 h-4 bg-gray-200 rounded animate-pulse"></div>

        {/* Grid skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="bg-gray-100 border border-gray-200 rounded-lg overflow-hidden">
              {/* Image skeleton */}
              <div className="aspect-square bg-gray-200 animate-pulse"></div>
              
              {/* Card content skeleton */}
              <div className="p-4">
                <div className="w-20 h-4 bg-gray-200 rounded animate-pulse mb-2"></div>
                <div className="w-32 h-4 bg-gray-200 rounded animate-pulse mb-3"></div>
                
                {/* Color dots skeleton */}
                <div className="flex space-x-1 mb-2">
                  {[1, 2, 3].map((j) => (
                    <div key={j} className="w-3 h-3 bg-gray-200 rounded-full animate-pulse"></div>
                  ))}
                </div>
                
                {/* Date skeleton */}
                <div className="w-24 h-3 bg-gray-200 rounded animate-pulse"></div>
              </div>
            </div>
          ))}
        </div>

        {/* Pagination skeleton */}
        <div className="flex justify-center space-x-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="w-10 h-10 bg-gray-200 rounded animate-pulse"></div>
          ))}
        </div>
      </div>
    </div>
  )
}
