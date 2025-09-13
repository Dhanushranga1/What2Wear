import { supabase } from './supabaseClient'

/**
 * Compresses an image file to WebP format using Canvas API
 * @param file - Original image file
 * @returns Promise<Blob> - Compressed WebP blob
 */
export async function compressImageToWebP(file: File): Promise<Blob> {
  // Reject files larger than 5MB before compression
  if (file.size > 5 * 1024 * 1024) {
    throw new Error('File too large (>5MB). Please choose a smaller image.')
  }

  // Check if it's an image file
  if (!file.type.startsWith('image/')) {
    throw new Error('Please select an image file.')
  }

  return new Promise((resolve, reject) => {
    const img = new Image()
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')

    if (!ctx) {
      reject(new Error('Canvas not supported'))
      return
    }

    img.onload = () => {
      // Calculate dimensions to fit within 1024px max
      let { width, height } = img
      const maxSize = 1024

      if (width > maxSize || height > maxSize) {
        if (width > height) {
          height = (height * maxSize) / width
          width = maxSize
        } else {
          width = (width * maxSize) / height
          height = maxSize
        }
      }

      // Set canvas dimensions
      canvas.width = width
      canvas.height = height

      // Draw and compress
      ctx.drawImage(img, 0, 0, width, height)

      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error('Failed to compress image'))
            return
          }

          // Check if compressed file is still too large (rare, but possible)
          if (blob.size > 500 * 1024) {
            reject(new Error('Image too large even after compression. Please choose a different image.'))
            return
          }

          resolve(blob)
        },
        'image/webp',
        0.6 // Quality setting
      )
    }

    img.onerror = () => {
      reject(new Error('Failed to load image'))
    }

    // Load the image
    img.src = URL.createObjectURL(file)
  })
}

/**
 * Uploads a garment image to Supabase Storage and returns a signed URL
 * @param file - Original image file
 * @param userId - Current user's ID
 * @returns Promise<{key: string, signedUrl: string}> - Storage key and signed URL
 */
export async function uploadGarmentImage(file: File, userId: string): Promise<{key: string, signedUrl: string}> {
  try {
    // Debug: Check current user
    const { data: { user } } = await supabase.auth.getUser()
    console.log('DEBUG: Current user:', user?.id)
    console.log('DEBUG: Provided userId:', userId)
    
    // Step 1: Compress the image
    const compressedBlob = await compressImageToWebP(file)

    // Step 2: Generate unique filename
    const uuid = crypto.randomUUID()
    const uploadKey = `${userId}/${uuid}.webp`  // For Supabase upload (relative to bucket)
    const fullPath = `wardrobe/${uploadKey}`    // For backend API (full path)
    console.log('DEBUG: Upload key:', uploadKey)
    console.log('DEBUG: Full path for backend:', fullPath)

    // Step 3: Upload to Supabase Storage
    console.log('DEBUG: About to upload to storage...')
    console.log('DEBUG: Upload key:', uploadKey)
    console.log('DEBUG: Blob size:', compressedBlob.size)
    
    const { data: uploadData, error: uploadError } = await supabase.storage
      .from('wardrobe')
      .upload(uploadKey, compressedBlob, {
        contentType: 'image/webp',
        upsert: false // Don't overwrite existing files
      })

    console.log('DEBUG: Upload result data:', uploadData)
    console.log('DEBUG: Upload error:', uploadError)

    if (uploadError) {
      console.error('DEBUG: Upload error details:', uploadError)
      throw new Error(`Upload failed: ${uploadError.message}`)
    }

    // Step 4: Create signed URL (7 days)
    const { data: signed } = await supabase.storage
      .from('wardrobe')
      .createSignedUrl(uploadKey, 60 * 60 * 24 * 7)

    if (!signed) {
      throw new Error('Could not create signed URL')
    }

    return { key: fullPath, signedUrl: signed.signedUrl }
  } catch (error) {
    console.error('Error in uploadGarmentImage:', error)
    throw error
  }
}
