# StyleSync Segmentation Service - Phase 1

A FastAPI microservice for clothing image segmentation using rembg (U²-Netp) and OpenCV GrabCut fallback.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- OpenCV system dependencies (installed via Dockerfile)
- 2GB+ RAM (for rembg model)

### Installation

```bash
# Install dependencies
make install

# Or manually
pip install -r requirements.txt
```

### Running the Service

```bash
# Development server with auto-reload
make run

# Or manually
uvicorn main:app --reload --port 8000
```

### Docker (Recommended for Production)

```bash
# Build and run
make build
make up

# Or manually
docker build -t stylesync-segmentation:dev .
docker run --rm -p 8000:8000 stylesync-segmentation:dev
```

## 📡 API Endpoints

### Health Check

```http
GET /stylesync/healthz
```

**Response:**
```json
{
  "ok": true,
  "version": "v1.0.0", 
  "service": "stylesync-segmentation"
}
```

### Segmentation

```http
POST /stylesync/segment
Content-Type: multipart/form-data
```

**Parameters:**
- `file` (required): JPG or PNG image file (max 10MB)
- `max_edge` (optional): Resize long edge to this size (256-4096px, default: 768)
- `gamma` (optional): Gamma correction value (0.8-2.2, default: 1.2)
- `engine` (optional): Segmentation engine (`auto|u2netp|grabcut`, default: `auto`)
- `morph_kernel` (optional): Morphological kernel size (1-7 odd, default: 3)
- `median_blur` (optional): Median blur size (0-9 odd, default: 5)

**Response:**
```json
{
  "engine": "u2netp",
  "width": 768,
  "height": 512,
  "mask_area_ratio": 0.43,
  "fallback_used": false,
  "artifacts": {
    "mask_png_b64": "<base64 PNG>",
    "item_rgba_png_b64": "<base64 PNG>",
    "bbox_xywh": [64, 22, 530, 468]
  },
  "debug": {
    "pre_gamma": 1.2,
    "morph_kernel": 3,
    "post_blur": 5
  }
}
```

### Metrics

```http
GET /stylesync/metrics
```

Returns service metrics including timing stats, counters, and mask quality metrics.

## 🧪 Testing

```bash
# Generate test images
make generate-test-images

# Run all tests
make test

# Run with coverage
make test-coverage

# Smoke test against running service
make smoke-test
make smoke-test-segment
```

## ⚡ Performance

**Targets (CPU baseline, max_edge=768):**
- P50: <400ms
- P95: <900ms

**Actual timings breakdown:**
- Decode + resize + gamma: 50-120ms
- rembg U²-Netp segmentation: 180-500ms
- Post-processing: 20-60ms

**Benchmark:**
```bash
make benchmark
```

## 🔧 Configuration

Environment variables:

```bash
# File limits
STYLESYNC_MAX_FILE_MB=10
STYLESYNC_MAX_EDGE=768
STYLESYNC_MIN_EDGE=256

# Processing
STYLESYNC_DEFAULT_GAMMA=1.2
STYLESYNC_ENGINE_DEFAULT=auto

# Logging
STYLESYNC_LOG_LEVEL=INFO

# Model cache
STYLESYNC_MODEL_CACHE=/root/.u2net/

# Feature flags
STYLESYNC_ENABLE_GRAYWORLD_WB=0
SEGMENT_FORCE_GRABCUT=0
```

## 🎯 Segmentation Engines

### Primary: rembg (U²-Netp)
- Fast, CPU-friendly deep learning model
- Good for most clothing items
- Automatic background removal

### Fallback: OpenCV GrabCut
- Traditional computer vision algorithm
- Central 70% rectangle initialization
- 5 iterations for speed/quality balance

### Engine Selection Logic
1. `engine=auto`: Try rembg → fallback to GrabCut if failed/poor mask
2. `engine=u2netp`: rembg only
3. `engine=grabcut`: GrabCut only

## 📊 Quality Metrics

**Mask Area Ratio:** Fraction of image that is garment (0.0-1.0)
- Good range: 0.03-0.98
- <0.03: Mask too small (segmentation failed)
- >0.98: Mask too large (background swallowed)

**Guardrails:**
- Returns 422 if mask quality outside acceptable range
- Provides actionable error messages

## 🛠️ Troubleshooting

### Common Issues

**Mask almost empty (ratio ~0.0)**
```bash
# Try higher gamma, larger kernel, or force GrabCut
curl -X POST "http://localhost:8000/stylesync/segment" \
  -F "file=@image.jpg" \
  -F "gamma=1.4" \
  -F "morph_kernel=5" \
  -F "engine=grabcut"
```

**Mask swallows entire image (ratio ~1.0)**
```bash
# Try lower gamma, smaller kernel
curl -X POST "http://localhost:8000/stylesync/segment" \
  -F "file=@image.jpg" \
  -F "gamma=1.0" \
  -F "morph_kernel=3"
```

**Jagged edges**
```bash
# Increase median blur
curl -X POST "http://localhost:8000/stylesync/segment" \
  -F "file=@image.jpg" \
  -F "median_blur=7"
```

**Performance issues**
- Ensure `max_edge` not too large
- Verify model cache is warm
- Check available RAM (rembg needs ~1GB)

### Debug Logging

```bash
export STYLESYNC_LOG_LEVEL=DEBUG
```

### Check Dependencies

```bash
make check-deps
```

## 🔒 Security

- File type validation (MIME + magic bytes)
- Size limits (10MB default)
- Dimension validation (min 256px)
- In-memory processing (no disk writes)
- Non-root container user

## 📈 Monitoring

The service exposes metrics via `/stylesync/metrics`:

```json
{
  "uptime_seconds": 3600,
  "counters": {
    "seg_requests_total": 150,
    "seg_engine_used_total_u2netp": 120,
    "seg_engine_used_total_grabcut": 30,
    "seg_fallback_total": 25
  },
  "timing_stats": {
    "total_duration_ms": {
      "count": 150,
      "mean": 320.5,
      "p50": 310,
      "p95": 850
    }
  }
}
```

## 🚧 Known Limitations (Phase 1)

- **Same-color backgrounds:** May include background when garment/background colors are very similar
- **Glossy fabrics:** May cause halos (partially mitigated by post-processing)
- **EXIF orientation:** Not handled (images should be pre-rotated)
- **Supported formats:** JPG/PNG only (no HEIC/WebP/GIF)

## 🔮 Future Enhancements (Phase 2+)

- Color extraction from segmented garments
- EXIF orientation handling
- Additional image formats
- GPU acceleration support
- Prometheus metrics export
- Object storage integration (replace base64)

## 📝 Example Usage

```bash
# Basic segmentation
curl -X POST "http://localhost:8000/stylesync/segment" \
  -F "file=@shirt.jpg"

# Custom parameters
curl -X POST "http://localhost:8000/stylesync/segment" \
  -F "file=@dress.png" \
  -F "max_edge=512" \
  -F "gamma=1.3" \
  -F "engine=auto" \
  -F "morph_kernel=5" \
  -F "median_blur=7"

# Decode mask for inspection
curl -s -X POST "http://localhost:8000/stylesync/segment" \
  -F "file=@image.jpg" | \
  jq -r '.artifacts.mask_png_b64' | \
  base64 -d > mask.png
```

## 🏗️ Development

```bash
# Format code
make format

# Run linting
make lint

# Get logs
make logs

# Shell into container
make shell
```

## 📄 License

Part of the What2Wear project. See project root for license information.
