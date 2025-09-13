# StyleSync Dockerfile - Phase 4 Production Ready
# Multi-stage build for security and optimization

FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
WORKDIR /app
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set metadata
LABEL org.opencontainers.image.title="StyleSync Backend"
LABEL org.opencontainers.image.description="StyleSync color matching API service"
LABEL org.opencontainers.image.version="1.0.0"

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r stylesync && useradd -r -g stylesync stylesync

# Copy Python packages from builder
COPY --from=builder /root/.local /home/stylesync/.local

# Set working directory
WORKDIR /app

# Copy application code with proper ownership
COPY --chown=stylesync:stylesync . .

# Create directories for cache and data
RUN mkdir -p /app/cache /app/data /app/logs \
    && chown -R stylesync:stylesync /app

# Switch to non-root user
USER stylesync

# Set environment variables
ENV PATH=/home/stylesync/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STYLESYNC_MODEL_CACHE=/app/cache

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/v1/healthz || exit 1
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app \
    && mkdir -p /root/.u2net \
    && chown -R app:app /root/.u2net

USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
