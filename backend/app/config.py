"""
StyleSync Configuration
Manages environment variables and defaults for all services including Phase 4.
"""
import os
from typing import Literal, Optional


class Config:
    """Configuration class for StyleSync services."""
    
    # File size and dimensions
    MAX_FILE_MB: int = int(os.environ.get("STYLESYNC_MAX_FILE_MB", "10"))
    MAX_EDGE: int = int(os.environ.get("STYLESYNC_MAX_EDGE", "768"))
    MIN_EDGE: int = int(os.environ.get("STYLESYNC_MIN_EDGE", "256"))
    
    # Image processing defaults
    DEFAULT_GAMMA: float = float(os.environ.get("STYLESYNC_DEFAULT_GAMMA", "1.2"))
    ENGINE_DEFAULT: Literal["auto", "u2netp", "grabcut"] = os.environ.get("STYLESYNC_ENGINE_DEFAULT", "auto")
    
    # Logging and caching
    LOG_LEVEL: str = os.environ.get("STYLESYNC_LOG_LEVEL", "INFO")
    MODEL_CACHE: str = os.environ.get("STYLESYNC_MODEL_CACHE", "/root/.u2net/")
    
    # Feature flags
    ENABLE_GRAYWORLD_WB: bool = bool(int(os.environ.get("STYLESYNC_ENABLE_GRAYWORLD_WB", "0")))
    SEGMENT_FORCE_GRABCUT: bool = bool(int(os.environ.get("SEGMENT_FORCE_GRABCUT", "0")))
    SEGMENT_ERODE_BEFORE_COLOR: bool = bool(int(os.environ.get("SEGMENT_ERODE_BEFORE_COLOR", "0")))
    
    # Phase 4 specific settings
    POLICY_VERSION: str = os.environ.get("STYLESYNC_POLICY_VERSION", "1.0.0")
    REDIS_URL: Optional[str] = os.environ.get("STYLESYNC_REDIS_URL")
    
    # Security settings
    API_KEY: Optional[str] = os.environ.get("STYLESYNC_API_KEY")
    API_KEYS: str = os.environ.get("STYLESYNC_API_KEYS", "")
    ENFORCE_HTTPS: bool = bool(int(os.environ.get("STYLESYNC_ENFORCE_HTTPS", "1")))
    ENABLE_AUTH: bool = bool(int(os.environ.get("STYLESYNC_ENABLE_AUTH", "1")))
    
    # CORS settings
    ALLOWED_ORIGINS: str = os.environ.get("STYLESYNC_ALLOWED_ORIGINS", "")
    ALLOWED_HOSTS: str = os.environ.get("STYLESYNC_ALLOWED_HOSTS", "*")
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = int(os.environ.get("STYLESYNC_RATE_LIMIT_REQUESTS", "60"))
    RATE_LIMIT_WINDOW: int = int(os.environ.get("STYLESYNC_RATE_LIMIT_WINDOW", "3600"))
    
    # Timeouts (milliseconds)
    TIMEOUT_SEGMENTATION: int = int(os.environ.get("STYLESYNC_TIMEOUT_SEGMENTATION", "1200"))
    TIMEOUT_EXTRACTION: int = int(os.environ.get("STYLESYNC_TIMEOUT_EXTRACTION", "300"))
    TIMEOUT_HARMONY: int = int(os.environ.get("STYLESYNC_TIMEOUT_HARMONY", "100"))
    TIMEOUT_TOTAL: int = int(os.environ.get("STYLESYNC_TIMEOUT_TOTAL", "2500"))
    
    # Observability
    JAEGER_ENDPOINT: Optional[str] = os.environ.get("STYLESYNC_JAEGER_ENDPOINT")
    METRICS_ENABLED: bool = bool(int(os.environ.get("STYLESYNC_METRICS_ENABLED", "1")))
    TRACING_ENABLED: bool = bool(int(os.environ.get("STYLESYNC_TRACING_ENABLED", "0")))
    
    # Cache TTLs (seconds)
    CACHE_TTL_L1_CONTENT: int = int(os.environ.get("STYLESYNC_CACHE_TTL_L1", "604800"))  # 7 days
    CACHE_TTL_L2_SEGMENTATION: int = int(os.environ.get("STYLESYNC_CACHE_TTL_L2_SEG", "86400"))  # 1 day
    CACHE_TTL_L2_EXTRACTION: int = int(os.environ.get("STYLESYNC_CACHE_TTL_L2_EXT", "86400"))  # 1 day
    CACHE_TTL_L2_ADVICE: int = int(os.environ.get("STYLESYNC_CACHE_TTL_L2_ADV", "43200"))  # 12 hours
    CACHE_TTL_IDEMPOTENCY: int = int(os.environ.get("STYLESYNC_CACHE_TTL_IDEM", "300"))  # 5 minutes
    
    # Mask quality thresholds
    MIN_MASK_AREA_RATIO: float = 0.03
    MAX_MASK_AREA_RATIO: float = 0.98
    
    # Supported image formats
    SUPPORTED_MIME_TYPES = ["image/jpeg", "image/png"]
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    
    @classmethod
    def validate_engine(cls, engine: str) -> bool:
        """Validate engine parameter."""
        return engine in ["auto", "u2netp", "grabcut"]
    
    @classmethod
    def validate_gamma(cls, gamma: float) -> bool:
        """Validate gamma parameter."""
        return 0.8 <= gamma <= 2.2
    
    @classmethod
    def validate_max_edge(cls, max_edge: int) -> bool:
        """Validate max_edge parameter."""
        return 256 <= max_edge <= 4096
    
    @classmethod
    def validate_kernel_size(cls, kernel: int) -> bool:
        """Validate morphological kernel size."""
        return 1 <= kernel <= 7 and kernel % 2 == 1
    
    @classmethod
    def validate_blur_size(cls, blur: int) -> bool:
        """Validate median blur size."""
        return 0 <= blur <= 9 and (blur == 0 or blur % 2 == 1)


# Global config instance
config = Config()
