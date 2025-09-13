# StyleSync Phase 4 API Documentation

## Overview

StyleSync Phase 4 introduces a unified, production-ready orchestrator API that provides comprehensive color advice through a single `/v1/advice` endpoint. The system integrates all Phase 1-3 capabilities with advanced caching, security, observability, and reliability features.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client App    │────│  Unified /v1 API │────│  Orchestrator   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                │                        ▼
                       ┌─────────────┐          ┌─────────────────┐
                       │  Security   │          │  Multi-Layer    │
                       │  & Auth     │          │  Cache System   │
                       └─────────────┘          └─────────────────┘
                                │                        │
                                │                        ▼
                       ┌─────────────┐          ┌─────────────────┐
                       │ Observability│          │  Phase 1→2→3    │
                       │ & Metrics   │          │  Pipeline       │
                       └─────────────┘          └─────────────────┘
```

## API Endpoints

### Primary Endpoint

#### `POST /v1/advice`

Unified endpoint providing complete color advice through three input modes:

**Input Modes:**

1. **Multipart Upload** - Direct file upload
2. **Presigned URL** - Upload via pre-signed S3 URL
3. **Direct Harmony** - Color harmony without image

**Authentication:**
- Header: `X-API-Key: <your-api-key>`
- Rate limit: 60 requests/hour (configurable)

### Multipart Upload Mode

Upload an image file directly:

```bash
curl -X POST "https://api.stylesync.com/v1/advice" \
  -H "X-API-Key: your-api-key" \
  -F "image=@wardrobe-item.jpg" \
  -F "target_role=bottom" \
  -F "phase3_color_intent=classic"
```

**Parameters:**
- `image` (file): Image file (PNG/JPEG, max 10MB)
- `target_role` (string): `top|bottom|outerwear|shoes|accessories|any`
- Phase-specific parameters (see below)

### Presigned Upload Mode

For large files or web applications:

```bash
# Step 1: Get presigned upload URL
curl -X POST "https://api.stylesync.com/v1/uploads/presign" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "jacket.jpg",
    "content_type": "image/jpeg"
  }'

# Response includes asset_id and upload_url

# Step 2: Upload to S3 (client-side)
curl -X PUT "https://s3.amazonaws.com/..." \
  -H "Content-Type: image/jpeg" \
  --data-binary @jacket.jpg

# Step 3: Get advice using asset_id
curl -X POST "https://api.stylesync.com/v1/advice" \
  -H "X-API-Key: your-api-key" \
  -d "asset_id=abc123&target_role=outerwear"
```

### Direct Harmony Mode

Generate color harmonies without image upload:

```bash
curl -X POST "https://api.stylesync.com/v1/advice" \
  -H "X-API-Key: your-api-key" \
  -d "base_color=%23FF0000&target_role=bottom&phase3_color_intent=bold"
```

**Parameters:**
- `base_color` (string): Hex color (e.g., `#FF0000`)
- `target_role` (string): Target garment role
- Phase 3 parameters for harmony customization

## Response Format

All modes return a consistent response structure:

```json
{
  "request_id": "req_abc123",
  "suggestions": [
    {
      "hex": "#FF6B6B",
      "role": "bottom",
      "harmony_type": "complementary",
      "confidence": 0.95,
      "saturation": 0.8,
      "lightness": 0.6
    }
  ],
  "meta": {
    "input_mode": "multipart_upload",
    "target_role": "bottom",
    "policy_version": "1.0.0",
    "phase1_results": {
      "segmentation_confidence": 0.92,
      "processing_time_ms": 1200
    },
    "phase2_results": {
      "dominant_colors": ["#2C3E50", "#E74C3C"],
      "extraction_confidence": 0.88,
      "processing_time_ms": 300
    },
    "phase3_results": {
      "harmony_algorithm": "complementary_advanced",
      "color_intent": "classic",
      "processing_time_ms": 100
    },
    "total_processing_time_ms": 1600,
    "cache_status": {
      "l1_hit": false,
      "l2_seg_hit": false,
      "l2_extract_hit": true,
      "l2_advice_hit": false
    },
    "degraded": false
  }
}
```

## Phase-Specific Parameters

### Phase 1 (Segmentation)
- `phase1_median_blur` (int): Noise reduction (1, 3, 5, 7, 9) - default: 3
- `phase1_confidence_threshold` (float): Min confidence (0.1-1.0) - default: 0.8
- `phase1_model_size` (int): Model resolution (256, 512, 768) - default: 768
- `phase1_post_processing` (string): `auto|aggressive|conservative` - default: auto

### Phase 2 (Color Extraction)
- `phase2_extraction_confidence` (float): Min confidence (0.1-1.0) - default: 0.7
- `phase2_color_space` (string): `rgb|hsv|lab` - default: rgb
- `phase2_clustering_method` (string): `kmeans|dbscan|meanshift` - default: kmeans
- `phase2_max_colors` (int): Max colors to extract (3-15) - default: 8

### Phase 3 (Color Harmony)
- `phase3_color_intent` (string): `classic|bold|subtle|monochromatic` - default: classic
- `phase3_target_saturation` (float): Desired saturation (0.0-1.0) - default: auto
- `phase3_target_lightness` (float): Desired lightness (0.0-1.0) - default: auto
- `phase3_harmony_strength` (float): Harmony intensity (0.1-1.0) - default: 0.8
- `phase3_color_temperature` (string): `warm|cool|neutral|auto` - default: auto

## Utility Endpoints

### Health Check
```bash
GET /v1/healthz
```
Returns service health status.

### Readiness Check
```bash
GET /v1/readyz
```
Returns service readiness including dependency status.

### Metrics
```bash
GET /v1/metrics
```
Returns Prometheus metrics for monitoring.

## Error Handling

The API uses standard HTTP status codes:

- `200 OK` - Success
- `400 Bad Request` - Invalid parameters
- `401 Unauthorized` - Invalid API key
- `413 Payload Too Large` - File too large (>10MB)
- `415 Unsupported Media Type` - Invalid image format
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Degraded mode or maintenance

Error responses include details:

```json
{
  "error": {
    "code": "INVALID_COLOR_FORMAT",
    "message": "Base color must be in hex format (e.g., #FF0000)",
    "request_id": "req_abc123"
  }
}
```

## Caching Strategy

Phase 4 implements multi-layer caching for optimal performance:

### L1 Cache - Content Deduplication
- **Purpose**: Avoid reprocessing identical images
- **TTL**: 7 days
- **Key**: SHA-256 + perceptual hash
- **Storage**: Redis primary, in-memory fallback

### L2 Cache - Phase Results
- **Segmentation Cache**: TTL 24 hours
- **Extraction Cache**: TTL 6 hours  
- **Advice Cache**: TTL 1 hour
- **Storage**: Redis with JSON serialization

### Cache Headers

Responses include cache information:

```
X-Cache-Status: HIT|MISS|STALE
X-Cache-TTL: 3600
X-Cache-Key: seg:abc123:v1.0.0:3:0.8:768:auto
```

## Performance Targets

Phase 4 maintains strict performance requirements:

- **P50 Latency**: ≤ 900ms (end-to-end)
- **P95 Latency**: ≤ 2000ms
- **Cache Hit Ratio**: ≥ 70% (steady state)
- **Availability**: ≥ 99.9%

### Performance by Input Mode

| Mode | Typical Latency | Cache Benefit |
|------|----------------|---------------|
| Direct Harmony | 50-200ms | High (90%+) |
| Cached Pipeline | 100-400ms | Medium (70%) |
| Full Pipeline | 800-1600ms | Low (20%) |

## Rate Limiting

API key-based rate limiting with configurable limits:

**Default Limits:**
- 60 requests per hour
- Burst allowance: 10 requests
- Rate limit headers included in responses:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1643723400
```

## Security Features

### Authentication
- API key authentication via `X-API-Key` header
- Keys validated against environment configuration
- Failed attempts logged for monitoring

### Input Validation
- File size limits (10MB max)
- Content-type validation
- Image format verification
- Parameter bounds checking
- SQL injection prevention

### CORS Policy
```json
{
  "allowed_origins": ["https://app.stylesync.com"],
  "allowed_methods": ["GET", "POST"],
  "allowed_headers": ["X-API-Key", "Content-Type"],
  "max_age": 86400
}
```

## Observability

### Structured Logging
All requests logged with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "level": "INFO",
  "request_id": "req_abc123",
  "user_id": "user_456",
  "endpoint": "/v1/advice",
  "input_mode": "multipart_upload",
  "processing_time_ms": 850,
  "cache_hits": {"l1": false, "l2_seg": true},
  "response_code": 200
}
```

### Metrics

Key metrics exposed via `/v1/metrics`:

```
# Request metrics
stylesync_requests_total{method="POST",endpoint="/v1/advice",status="200"} 1547
stylesync_request_duration_seconds{endpoint="/v1/advice",quantile="0.5"} 0.85
stylesync_request_duration_seconds{endpoint="/v1/advice",quantile="0.95"} 1.95

# Cache metrics
stylesync_cache_hits_total{layer="l1"} 892
stylesync_cache_misses_total{layer="l1"} 234
stylesync_cache_hit_ratio{layer="l1"} 0.79

# Phase metrics
stylesync_phase_duration_seconds{phase="segmentation",quantile="0.5"} 1.2
stylesync_phase_duration_seconds{phase="extraction",quantile="0.5"} 0.3
stylesync_phase_duration_seconds{phase="harmony",quantile="0.5"} 0.1

# Error metrics
stylesync_errors_total{type="validation"} 23
stylesync_errors_total{type="timeout"} 5
stylesync_errors_total{type="degradation"} 12
```

### Distributed Tracing

OpenTelemetry tracing for request flow:

```
Trace: req_abc123
├── span: request_validation (2ms)
├── span: authentication (5ms)
├── span: fingerprint_generation (15ms)
├── span: cache_lookup_l1 (3ms)
├── span: phase1_segmentation (1200ms)
├── span: cache_store_l2_seg (8ms)
├── span: phase2_extraction (300ms)
├── span: phase3_harmony (100ms)
└── span: response_serialization (12ms)
```

## Degradation and Reliability

### Circuit Breakers
- Per-phase circuit breakers
- Failure threshold: 5 failures in 60 seconds
- Recovery timeout: 30 seconds
- Half-open testing with single request

### Timeout Management
- Phase 1: 1200ms timeout
- Phase 2: 300ms timeout  
- Phase 3: 100ms timeout
- Overall request: 2000ms timeout

### Graceful Degradation

When components fail, the system provides fallback responses:

```json
{
  "request_id": "req_abc123",
  "suggestions": [
    {
      "hex": "#808080",
      "role": "bottom",
      "harmony_type": "neutral_fallback",
      "confidence": 0.5
    }
  ],
  "meta": {
    "degraded": true,
    "fallback_reason": "segmentation_timeout",
    "original_error": "Phase 1 processing exceeded 1200ms timeout"
  }
}
```

## SDK Examples

### Python

```python
import requests

class StyleSyncClient:
    def __init__(self, api_key, base_url="https://api.stylesync.com"):
        self.api_key = api_key
        self.base_url = base_url
    
    def get_advice(self, image_path, target_role="any", **kwargs):
        """Get color advice for an image."""
        with open(image_path, 'rb') as f:
            files = {'image': f}
            data = {'target_role': target_role, **kwargs}
            headers = {'X-API-Key': self.api_key}
            
            response = requests.post(
                f"{self.base_url}/v1/advice",
                files=files,
                data=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    
    def get_harmony(self, base_color, target_role, **kwargs):
        """Get color harmony without image."""
        params = {
            'base_color': base_color,
            'target_role': target_role,
            **kwargs
        }
        headers = {'X-API-Key': self.api_key}
        
        response = requests.post(
            f"{self.base_url}/v1/advice",
            params=params,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = StyleSyncClient("your-api-key")

# Image analysis
result = client.get_advice(
    "jacket.jpg",
    target_role="outerwear",
    phase3_color_intent="bold"
)

# Direct harmony
harmony = client.get_harmony(
    "#FF0000",
    "bottom",
    phase3_color_intent="classic"
)
```

### JavaScript/TypeScript

```typescript
interface StyleSyncResponse {
  request_id: string;
  suggestions: Array<{
    hex: string;
    role: string;
    harmony_type: string;
    confidence: number;
  }>;
  meta: {
    input_mode: string;
    target_role: string;
    total_processing_time_ms: number;
    degraded: boolean;
  };
}

class StyleSyncClient {
  constructor(
    private apiKey: string,
    private baseUrl = "https://api.stylesync.com"
  ) {}

  async getAdvice(
    image: File,
    targetRole: string,
    options: Record<string, any> = {}
  ): Promise<StyleSyncResponse> {
    const formData = new FormData();
    formData.append('image', image);
    formData.append('target_role', targetRole);
    
    Object.entries(options).forEach(([key, value]) => {
      formData.append(key, value.toString());
    });

    const response = await fetch(`${this.baseUrl}/v1/advice`, {
      method: 'POST',
      headers: {
        'X-API-Key': this.apiKey,
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  }

  async getHarmony(
    baseColor: string,
    targetRole: string,
    options: Record<string, any> = {}
  ): Promise<StyleSyncResponse> {
    const params = new URLSearchParams({
      base_color: baseColor,
      target_role: targetRole,
      ...options,
    });

    const response = await fetch(`${this.baseUrl}/v1/advice`, {
      method: 'POST',
      headers: {
        'X-API-Key': this.apiKey,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  }
}

// Usage
const client = new StyleSyncClient('your-api-key');

// File upload
const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
const file = fileInput.files?.[0];

if (file) {
  const result = await client.getAdvice(file, 'bottom', {
    phase3_color_intent: 'classic'
  });
  console.log('Suggestions:', result.suggestions);
}
```

## Migration from Phase 3

Existing Phase 1-3 integrations can migrate incrementally:

### Option 1: Direct Migration
Replace individual phase endpoints with unified `/v1/advice`:

```diff
- POST /segment (Phase 1)
- POST /extract (Phase 2)  
- POST /harmony (Phase 3)
+ POST /v1/advice (unified)
```

### Option 2: Gradual Migration
Use unified API for new features while maintaining legacy endpoints.

### Breaking Changes
- Authentication now required for all endpoints
- Response format includes additional metadata
- Error codes standardized to HTTP conventions
- Rate limiting enforced by default

## Deployment Guide

### Environment Variables

```bash
# Core Configuration
STYLESYNC_ENVIRONMENT=production
STYLESYNC_API_VERSION=1.0.0
STYLESYNC_LOG_LEVEL=INFO

# Security
STYLESYNC_API_KEY=your-production-api-key
STYLESYNC_ALLOWED_ORIGINS=https://app.stylesync.com
STYLESYNC_RATE_LIMIT_REQUESTS=60
STYLESYNC_RATE_LIMIT_WINDOW=3600

# Caching
STYLESYNC_REDIS_URL=redis://localhost:6379
STYLESYNC_CACHE_L1_TTL=604800  # 7 days
STYLESYNC_CACHE_L2_SEG_TTL=86400  # 24 hours
STYLESYNC_CACHE_L2_EXTRACT_TTL=21600  # 6 hours
STYLESYNC_CACHE_L2_ADVICE_TTL=3600  # 1 hour

# Storage
STYLESYNC_S3_BUCKET=stylesync-uploads
STYLESYNC_S3_REGION=us-east-1
STYLESYNC_PRESIGNED_TTL=3600

# Timeouts (milliseconds)
STYLESYNC_PHASE1_TIMEOUT_MS=1200
STYLESYNC_PHASE2_TIMEOUT_MS=300
STYLESYNC_PHASE3_TIMEOUT_MS=100
STYLESYNC_REQUEST_TIMEOUT_MS=2000

# Observability
STYLESYNC_ENABLE_TRACING=true
STYLESYNC_TRACING_ENDPOINT=http://jaeger:14268/api/traces
STYLESYNC_METRICS_PORT=8081
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r stylesync && useradd -r -g stylesync stylesync

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ app/
COPY main.py .
RUN chown -R stylesync:stylesync /app

# Switch to non-root user
USER stylesync

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/v1/healthz || exit 1

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stylesync-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: stylesync-api
  template:
    metadata:
      labels:
        app: stylesync-api
    spec:
      containers:
      - name: api
        image: stylesync/api:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: STYLESYNC_REDIS_URL
          value: "redis://redis-service:6379"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /v1/healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /v1/readyz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: stylesync-api-service
spec:
  selector:
    app: stylesync-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Request Metrics**
   - Request rate (requests/second)
   - Response time (P50, P95, P99)
   - Error rate by status code

2. **Cache Performance**
   - Hit ratio by cache layer
   - Cache response time
   - Cache storage utilization

3. **Phase Performance**
   - Processing time per phase
   - Phase success rate
   - Timeout frequency

4. **Resource Utilization**
   - CPU usage
   - Memory usage
   - Network I/O
   - Storage I/O

### Recommended Alerts

```yaml
# High error rate
- alert: HighErrorRate
  expr: rate(stylesync_requests_total{status!="200"}[5m]) > 0.1
  for: 2m
  annotations:
    summary: "High error rate detected"

# High response time
- alert: HighLatency
  expr: histogram_quantile(0.95, rate(stylesync_request_duration_seconds_bucket[5m])) > 2.0
  for: 5m
  annotations:
    summary: "95th percentile latency above 2 seconds"

# Cache degradation
- alert: LowCacheHitRate
  expr: stylesync_cache_hit_ratio < 0.5
  for: 10m
  annotations:
    summary: "Cache hit rate below 50%"

# Service unavailable
- alert: ServiceDown
  expr: up{job="stylesync-api"} == 0
  for: 1m
  annotations:
    summary: "StyleSync API service is down"
```

---

## API Reference Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/advice` | POST | Unified color advice endpoint |
| `/v1/uploads/presign` | POST | Generate presigned upload URL |
| `/v1/healthz` | GET | Health check |
| `/v1/readyz` | GET | Readiness check |
| `/v1/metrics` | GET | Prometheus metrics |

For additional support or questions, consult the troubleshooting guide or contact the StyleSync API team.
