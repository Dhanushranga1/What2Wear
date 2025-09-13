"use client"
import { useState } from "react"
import { supabase } from "../../../../lib/supabaseClient"
import { uploadGarmentImage } from "../../../../lib/storage"

interface GarmentData {
  id: string
  color_bins: string[]
}

export default function UploadPage() {
  const [preview, setPreview] = useState<string | null>(null)
  const [status, setStatus] = useState<string>("")
  const [uploading, setUploading] = useState(false)
  const [uploadedPath, setUploadedPath] = useState<string | null>(null)
  const [savedGarment, setSavedGarment] = useState<GarmentData | null>(null)
  
  // Form data for garment creation
  const [category, setCategory] = useState<string>("top")
  const [subtype, setSubtype] = useState<string>("")
  const [metaTags, setMetaTags] = useState<string>("")

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      setStatus("Uploading...")
      setPreview(null)
      setUploadedPath(null)
      setSavedGarment(null)

      const user = (await supabase.auth.getUser()).data.user
      if (!user) {
        throw new Error("Not logged in")
      }

      const { key, signedUrl } = await uploadGarmentImage(file, user.id)
      setPreview(signedUrl)
      setUploadedPath(key)
      setStatus("Upload successful! Now add details to save as garment.")
    } catch (err: any) {
      setStatus("Error: " + err.message)
      setPreview(null)
      setUploadedPath(null)
    } finally {
      setUploading(false)
    }
  }

  const handleSaveGarment = async () => {
    if (!uploadedPath) {
      setStatus("Error: No image uploaded")
      return
    }

    try {
      setStatus("Saving garment...")
      
      const user = (await supabase.auth.getUser()).data.user
      if (!user) {
        throw new Error("Not logged in")
      }

      // Get auth token
      const { data: { session } } = await supabase.auth.getSession()
      if (!session?.access_token) {
        throw new Error("No auth token")
      }

      // Parse meta tags
      const tags = metaTags
        .split(",")
        .map(tag => tag.trim())
        .filter(tag => tag.length > 0)
        .slice(0, 10) // Max 10 tags

      // Call backend API
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/garments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          image_path: uploadedPath,
          category,
          subtype: subtype.trim() || undefined,
          meta_tags: tags
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "Failed to save garment")
      }

      const garmentData = await response.json()
      setSavedGarment(garmentData)
      setStatus("Garment saved successfully!")

    } catch (err: any) {
      setStatus("Error: " + err.message)
    }
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Upload Garment</h1>
      
      <div className="space-y-6">
        {/* Step 1: File Upload */}
        <div>
          <h2 className="text-lg font-medium text-gray-900 mb-2">Step 1: Upload Image</h2>
          <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-2">
            Select an image
          </label>
          <input
            id="file-input"
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            disabled={uploading}
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-full file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-50 file:text-blue-700
              hover:file:bg-blue-100
              disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        {/* Step 2: Garment Details (only show after upload) */}
        {uploadedPath && !savedGarment && (
          <div>
            <h2 className="text-lg font-medium text-gray-900 mb-4">Step 2: Add Garment Details</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Category */}
              <div>
                <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
                  Category *
                </label>
                <select
                  id="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="top">Top</option>
                  <option value="bottom">Bottom</option>
                  <option value="one_piece">One Piece</option>
                </select>
              </div>

              {/* Subtype */}
              <div>
                <label htmlFor="subtype" className="block text-sm font-medium text-gray-700 mb-1">
                  Subtype (optional)
                </label>
                <input
                  id="subtype"
                  type="text"
                  value={subtype}
                  onChange={(e) => setSubtype(e.target.value)}
                  placeholder="e.g., t-shirt, jeans, dress"
                  maxLength={40}
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            {/* Meta Tags */}
            <div className="mt-4">
              <label htmlFor="meta-tags" className="block text-sm font-medium text-gray-700 mb-1">
                Tags (optional)
              </label>
              <input
                id="meta-tags"
                type="text"
                value={metaTags}
                onChange={(e) => setMetaTags(e.target.value)}
                placeholder="e.g., casual, summer, work (comma-separated)"
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Up to 10 tags, each max 24 characters
              </p>
            </div>

            {/* Save Button */}
            <div className="mt-4">
              <button
                onClick={handleSaveGarment}
                disabled={!category}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save Garment
              </button>
            </div>
          </div>
        )}

        {/* Status Message */}
        {status && (
          <div className={`p-3 rounded-md ${
            status.startsWith("Error") 
              ? "bg-red-50 text-red-800 border border-red-200" 
              : status.includes("successful")
              ? "bg-green-50 text-green-800 border border-green-200"
              : "bg-blue-50 text-blue-800 border border-blue-200"
          }`}>
            {status}
          </div>
        )}

        {/* Loading Indicator */}
        {uploading && (
          <div className="flex items-center space-x-2 text-blue-600">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span className="text-sm">Processing image...</span>
          </div>
        )}

        {/* Preview */}
        {preview && (
          <div className="mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Preview:</h3>
            <img 
              src={preview} 
              alt="Uploaded preview" 
              className="max-w-xs rounded-lg shadow-md border border-gray-200"
            />
          </div>
        )}

        {/* Saved Garment Confirmation */}
        {savedGarment && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md">
            <h3 className="text-lg font-medium text-green-900 mb-2">✅ Garment Saved!</h3>
            <p className="text-sm text-green-700 mb-2">
              <strong>ID:</strong> {savedGarment.id}
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-green-700 font-medium">Color Bins:</span>
              {savedGarment.color_bins.map((bin, index) => (
                <span
                  key={index}
                  className="inline-block px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full"
                >
                  {bin}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="mt-6 p-4 bg-gray-50 rounded-md">
          <h4 className="text-sm font-medium text-gray-900 mb-2">How it works:</h4>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>• Images are compressed to WebP format (max 1024px, &lt;200KB typical)</li>
            <li>• AI extracts color palette automatically</li>
            <li>• Garments are saved to your private wardrobe</li>
            <li>• Maximum file size: 5MB</li>
            <li>• Supported formats: JPG, PNG, WebP</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
