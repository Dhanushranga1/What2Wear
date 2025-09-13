# What2Wear StyleSync ColorMatch API Documentation

## Phase 2 Color Extraction Pipeline

The What2Wear color extraction API provides sophisticated garment color analysis using advanced computer vision and machine learning techniques. This documentation covers the StyleSync ColorMatch MVP implementation.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Color Extraction Endpoints](#color-extraction-endpoints)
4. [Request/Response Formats](#request-response-formats)
5. [Algorithm Parameters](#algorithm-parameters)
6. [Error Handling](#error-handling)
7. [Observability & Monitoring](#observability--monitoring)
8. [Integration Examples](#integration-examples)
9. [Performance Guidelines](#performance-guidelines)

## Overview

The color extraction pipeline analyzes garment images to:
- Extract dominant colors using MiniBatchKMeans clustering
- Select optimal base colors with neutral penalties and spatial cohesion
- Provide color harmony analysis for future matching phases
- Generate comprehensive metadata and performance metrics

### Key Features

- **Advanced Color Clustering**: MiniBatchKMeans with HSV filtering
- **Smart Base Selection**: Neutral color penalties and spatial cohesion analysis
- **Performance Optimized**: Sub-100ms extraction for typical garment images
- **Comprehensive Logging**: Full observability with metrics collection
- **Flexible Parameters**: Configurable clustering, filtering, and selection

## Authentication

All API endpoints require authentication using Supabase JWT tokens.

```http
Authorization: Bearer <supabase_jwt_token>
```

## Color Extraction Endpoints

### Extract Colors - Direct Mode

Extract colors directly from base64-encoded image and mask data.

```http
POST /colors/extract
Content-Type: application/json
```

**Request Body:**
```json
{
  "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "mask_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "n_clusters": 5,
  "erosion_iterations": 2,
  "max_samples": 10000,
  "shadow_threshold": 0.3,
  "neutral_penalty_weight": 0.5,
  "cohesion_enabled": true,
  "cohesion_weight": 0.10
}
```

**Response:**
```json
{
  "palette": [
    {
      "hex": "#2E4A6B",
      "rgb": [46, 74, 107],
      "ratio": 0.65,
      "is_base": true
    },
    {
      "hex": "#F5F5DC",
      "rgb": [245, 245, 220],
      "ratio": 0.35,
      "is_base": false
    }
  ],
  "base_color": {
    "hex": "#2E4A6B",
    "rgb": [46, 74, 107],
    "ratio": 0.65,
    "is_base": true
  },
  "base_color_index": 0,
  "harmony_analysis": {
    "harmony_type": "complementary",
    "diversity_score": 0.68,
    "color_relationships": [
      {
        "color1": "#2E4A6B",
        "color2": "#F5F5DC",
        "distance": 173.2
      }
    ],
    "temperature_balance": "cool"
  },
  "metadata": {
    "cluster_count": 2,
    "total_pixels_analyzed": 8543,
    "mask_pixel_count": 12456,
    "extraction_id": "extraction_1",
    "performance": {
      "total_duration_ms": 87.3,
      "clustering_duration_ms": 34.7,
      "base_selection_duration_ms": 12.4,
      "memory_peak_mb": 42.8
    },
    "algorithm_params": {
      "n_clusters": 5,
      "erosion_iterations": 2,
      "max_samples": 10000,
      "shadow_threshold": 0.3,
      "neutral_penalty_weight": 0.5,
      "cohesion_enabled": true,
      "cohesion_weight": 0.10
    }
  }
}
```

### Extract Colors - One-Shot Mode

Extract colors from uploaded files with automatic garment detection.

```http
POST /colors/extract-file
Content-Type: multipart/form-data
```

**Form Parameters:**
- `image`: Image file (JPEG, PNG, WebP)
- `mask`: Mask file (optional - if not provided, automatic segmentation)
- `n_clusters`: Number of color clusters (default: 5)
- `erosion_iterations`: Mask erosion iterations (default: 2)
- `max_samples`: Maximum pixel samples (default: 10000)
- Additional algorithm parameters as form fields

## Request/Response Formats

### Color Object

```json
{
  "hex": "#2E4A6B",        // Hex color code
  "rgb": [46, 74, 107],    // RGB values [0-255]
  "ratio": 0.65,           // Proportion of total garment (0-1)
  "is_base": true          // Whether this is the selected base color
}
```

### Harmony Analysis Object

```json
{
  "harmony_type": "complementary",  // monochromatic, analogous, complementary, triadic
  "diversity_score": 0.68,         // Color diversity metric [0-1]
  "color_relationships": [         // Pairwise color relationships
    {
      "color1": "#2E4A6B",
      "color2": "#F5F5DC", 
      "distance": 173.2           // Euclidean distance in RGB space
    }
  ],
  "temperature_balance": "cool"    // warm, cool, balanced
}
```

### Performance Metadata

```json
{
  "total_duration_ms": 87.3,        // Total extraction time
  "clustering_duration_ms": 34.7,   // K-means clustering time
  "base_selection_duration_ms": 12.4, // Base color selection time
  "memory_peak_mb": 42.8            // Peak memory usage
}
```

## Algorithm Parameters

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_clusters` | int | 5 | Number of color clusters for K-means |
| `erosion_iterations` | int | 2 | Mask erosion for edge cleanup |
| `max_samples` | int | 10000 | Maximum pixels to sample |

### Filtering Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `shadow_threshold` | float | 0.3 | HSV V threshold for shadow filtering |
| `neutral_penalty_weight` | float | 0.5 | Penalty multiplier for neutral colors |
| `cohesion_enabled` | bool | true | Enable spatial cohesion analysis |
| `cohesion_weight` | float | 0.10 | Weight for spatial cohesion bonus |

### Advanced Parameters

```json
{
  "gamma_correction": 1.2,          // Gamma correction factor
  "min_saturation": 0.0,           // Minimum saturation filter
  "specular_filtering": true,       // Remove specular highlights
  "edge_exclusion_pixels": 1       // Pixels to exclude from mask edges
}
```

## Error Handling

### Error Response Format

```json
{
  "detail": "Error description",
  "error_code": "VALIDATION_ERROR",
  "extraction_id": "extraction_123" // If extraction was started
}
```

### Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `INVALID_IMAGE_FORMAT` | Unsupported image format | Use JPEG, PNG, or WebP |
| `MASK_SIZE_MISMATCH` | Image and mask dimensions differ | Ensure same dimensions |
| `INSUFFICIENT_PIXELS` | Too few garment pixels after filtering | Reduce erosion or increase mask |
| `CLUSTERING_FAILED` | K-means clustering failed | Reduce n_clusters or increase samples |
| `BASE_SELECTION_ERROR` | Base color selection failed | Check neutral penalty parameters |

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (validation error)
- `401`: Unauthorized (invalid token)
- `413`: Payload Too Large (image too big)
- `422`: Unprocessable Entity (algorithm error)
- `500`: Internal Server Error

## Observability & Monitoring

### Health Check

```http
GET /metrics/health
```

**Response:**
```json
{
  "timestamp": 1694612345.67,
  "memory_usage_mb": 156.7,
  "memory_percent": 12.3,
  "cpu_percent": 8.5,
  "disk_usage_percent": 45.2,
  "uptime_seconds": 86400,
  "status": "healthy"
}
```

### Performance Metrics

```http
GET /metrics/summary
```

**Response:**
```json
{
  "total_operations": 1247,
  "total_errors": 12,
  "overall_error_rate": 0.0096,
  "operations": {
    "color_clustering": {
      "total_calls": 1247,
      "error_count": 3,
      "error_rate": 0.0024,
      "duration_stats": {
        "mean_ms": 34.7,
        "median_ms": 32.1,
        "p95_ms": 67.8,
        "p99_ms": 89.2
      }
    }
  }
}
```

### Operation-Specific Stats

```http
GET /metrics/operations/color_clustering
```

## Integration Examples

### Frontend JavaScript Integration

```javascript
// Extract colors from uploaded image
async function extractColors(imageFile, maskFile) {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('mask', maskFile);
  formData.append('n_clusters', '5');
  formData.append('cohesion_enabled', 'true');
  
  const response = await fetch('/colors/extract-file', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${supabaseToken}`
    },
    body: formData
  });
  
  if (!response.ok) {
    throw new Error(`Color extraction failed: ${response.statusText}`);
  }
  
  return await response.json();
}

// Use extracted colors
extractColors(imageFile, maskFile)
  .then(result => {
    const baseColor = result.base_color;
    const palette = result.palette;
    const harmony = result.harmony_analysis;
    
    console.log(`Base color: ${baseColor.hex}`);
    console.log(`Harmony type: ${harmony.harmony_type}`);
    console.log(`Extraction took ${result.metadata.performance.total_duration_ms}ms`);
  })
  .catch(error => {
    console.error('Color extraction error:', error);
  });
```

### Python Client Integration

```python
import requests
import base64
from PIL import Image
import io

def extract_colors_direct(image_path, mask_path, token):
    # Load and encode images
    with open(image_path, 'rb') as f:
        image_b64 = base64.b64encode(f.read()).decode()
    
    with open(mask_path, 'rb') as f:
        mask_b64 = base64.b64encode(f.read()).decode()
    
    # Make request
    response = requests.post(
        'http://localhost:8000/colors/extract',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'image_data': f'data:image/png;base64,{image_b64}',
            'mask_data': f'data:image/png;base64,{mask_b64}',
            'n_clusters': 5,
            'cohesion_enabled': True
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        return result
    else:
        raise Exception(f"API error: {response.text}")

# Usage
result = extract_colors_direct('shirt.jpg', 'shirt_mask.png', 'jwt_token')
base_color = result['base_color']['hex']
performance = result['metadata']['performance']
```

### Batch Processing Example

```python
import asyncio
import aiohttp

async def extract_colors_batch(image_paths, token):
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        for image_path in image_paths:
            # Prepare form data
            with open(image_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('image', f, filename='image.jpg')
                data.add_field('n_clusters', '5')
                
                task = session.post(
                    'http://localhost:8000/colors/extract-file',
                    headers={'Authorization': f'Bearer {token}'},
                    data=data
                )
                tasks.append(task)
        
        # Execute batch requests
        responses = await asyncio.gather(*tasks)
        results = []
        
        for response in responses:
            if response.status == 200:
                result = await response.json()
                results.append(result)
            else:
                results.append(None)
        
        return results
```

## Performance Guidelines

### Image Specifications

- **Recommended size**: 512×512 to 1024×1024 pixels
- **Maximum size**: 2048×2048 pixels
- **Formats**: JPEG (quality ≥85%), PNG, WebP
- **File size**: ≤5MB per image

### Optimization Tips

1. **Pre-process images**: Resize large images before upload
2. **Optimize masks**: Use binary masks (0/255) for best performance
3. **Tune parameters**: 
   - Use `n_clusters=3-7` for most garments
   - Set `max_samples=5000-15000` based on detail needs
   - Enable `cohesion_enabled=true` for better base color selection

### Performance Expectations

| Image Size | Typical Duration | Memory Usage |
|------------|------------------|--------------|
| 256×256 | 15-30ms | 25-40MB |
| 512×512 | 30-60ms | 40-70MB |
| 1024×1024 | 60-120ms | 70-150MB |
| 2048×2048 | 120-300ms | 150-400MB |

### Rate Limiting

- **Per user**: 100 requests/minute
- **Per IP**: 1000 requests/hour
- **Burst limit**: 10 concurrent requests

### Monitoring Integration

```javascript
// Monitor extraction performance
function trackExtractionMetrics(result) {
  const performance = result.metadata.performance;
  
  // Send to analytics
  analytics.track('color_extraction_completed', {
    duration_ms: performance.total_duration_ms,
    memory_mb: performance.memory_peak_mb,
    cluster_count: result.metadata.cluster_count,
    pixel_count: result.metadata.total_pixels_analyzed,
    harmony_type: result.harmony_analysis.harmony_type
  });
  
  // Performance alerts
  if (performance.total_duration_ms > 200) {
    console.warn('Slow color extraction detected');
  }
}
```

## Next Steps

This Phase 2 documentation covers the complete color extraction pipeline. For Phase 3 integration:

1. **Outfit Matching**: Use extracted palettes for garment compatibility scoring
2. **Style Analysis**: Leverage harmony metrics for style classification  
3. **Recommendation Engine**: Integrate color data with user preferences
4. **Advanced Filtering**: Use base colors for wardrobe organization

For questions or support, please refer to the observability endpoints for real-time performance data and system health.
