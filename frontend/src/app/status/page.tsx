export default function StatusPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-4xl mx-auto px-4">
        <div className="bg-white shadow rounded-lg p-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">
            What2Wear - Phase 1 Status
          </h1>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800">✅ Completed Features</h2>
              
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <span className="text-green-600">✓</span>
                  <span>Login page with email/password</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-green-600">✓</span>
                  <span>Signup page with user registration</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-green-600">✓</span>
                  <span>Protected app shell and routes</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-green-600">✓</span>
                  <span>Session management & persistence</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-green-600">✓</span>
                  <span>User header with logout functionality</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-green-600">✓</span>
                  <span>Placeholder pages (wardrobe, upload, item)</span>
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-800">🔗 Test Links</h2>
              
              <div className="space-y-2">
                <a 
                  href="/login" 
                  className="block text-blue-600 hover:text-blue-800 underline"
                >
                  → Login Page
                </a>
                <a 
                  href="/signup" 
                  className="block text-blue-600 hover:text-blue-800 underline"
                >
                  → Signup Page  
                </a>
                <a 
                  href="/wardrobe" 
                  className="block text-blue-600 hover:text-blue-800 underline"
                >
                  → Wardrobe (protected)
                </a>
                <a 
                  href="/upload" 
                  className="block text-blue-600 hover:text-blue-800 underline"
                >
                  → Upload (protected)
                </a>
                <a 
                  href="/item/123" 
                  className="block text-blue-600 hover:text-blue-800 underline"
                >
                  → Item Detail (protected)
                </a>
              </div>
            </div>
          </div>
          
          <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded">
            <h3 className="font-semibold text-yellow-800 mb-2">⚠️ Setup Required</h3>
            <p className="text-yellow-700 text-sm">
              To test authentication, create a Supabase project and update the environment variables in 
              <code className="bg-yellow-100 px-1 rounded">.env.local</code>
            </p>
          </div>
          
          <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded">
            <h3 className="font-semibold text-green-800 mb-2">🎉 Phase 1 Complete!</h3>
            <p className="text-green-700 text-sm">
              Authentication system and protected app shell are ready. 
              Next: Phase 2 will add image upload and garment management.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
