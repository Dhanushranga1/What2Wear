"""
StyleSync Security & Authentication System
API key authentication, CORS controls, input validation, and security middleware.
"""
import hashlib
import hmac
import os
import secrets
import time
from typing import Dict, List, Optional, Set
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages API key authentication and validation."""
    
    def __init__(self):
        # Load API keys from environment
        self.api_keys: Set[str] = set()
        self._load_api_keys()
        
        # Rate limiting storage (in-memory for MVP)
        self.rate_limit_storage: Dict[str, List[float]] = {}
        
        # Security settings
        self.rate_limit_requests = int(os.environ.get("STYLESYNC_RATE_LIMIT_REQUESTS", "60"))
        self.rate_limit_window = int(os.environ.get("STYLESYNC_RATE_LIMIT_WINDOW", "3600"))  # 1 hour
        
    def _load_api_keys(self):
        """Load API keys from environment variables."""
        # Primary API key
        primary_key = os.environ.get("STYLESYNC_API_KEY")
        if primary_key:
            self.api_keys.add(primary_key.strip())
        
        # Additional API keys (comma-separated)
        additional_keys = os.environ.get("STYLESYNC_API_KEYS", "")
        if additional_keys:
            for key in additional_keys.split(","):
                key = key.strip()
                if key:
                    self.api_keys.add(key)
        
        if not self.api_keys:
            logger.warning("No API keys configured - authentication disabled")
    
    def validate_api_key(self, api_key: str) -> bool:
        """Validate API key using secure comparison."""
        if not self.api_keys:
            # If no keys configured, allow access (development mode)
            return True
        
        # Use constant-time comparison to prevent timing attacks
        for valid_key in self.api_keys:
            if hmac.compare_digest(api_key, valid_key):
                return True
        
        return False
    
    def check_rate_limit(self, api_key: str) -> bool:
        """Check if API key is within rate limits."""
        current_time = time.time()
        window_start = current_time - self.rate_limit_window
        
        # Clean old entries
        if api_key in self.rate_limit_storage:
            self.rate_limit_storage[api_key] = [
                timestamp for timestamp in self.rate_limit_storage[api_key]
                if timestamp > window_start
            ]
        else:
            self.rate_limit_storage[api_key] = []
        
        # Check limit
        request_count = len(self.rate_limit_storage[api_key])
        if request_count >= self.rate_limit_requests:
            return False
        
        # Record this request
        self.rate_limit_storage[api_key].append(current_time)
        return True
    
    def get_rate_limit_status(self, api_key: str) -> Dict[str, int]:
        """Get current rate limit status for API key."""
        current_time = time.time()
        window_start = current_time - self.rate_limit_window
        
        if api_key in self.rate_limit_storage:
            recent_requests = [
                timestamp for timestamp in self.rate_limit_storage[api_key]
                if timestamp > window_start
            ]
            remaining = max(0, self.rate_limit_requests - len(recent_requests))
        else:
            remaining = self.rate_limit_requests
        
        return {
            "limit": self.rate_limit_requests,
            "remaining": remaining,
            "window_seconds": self.rate_limit_window
        }


class SecurityManager:
    """Main security manager for StyleSync."""
    
    def __init__(self):
        self.api_key_manager = APIKeyManager()
        self.security_scheme = HTTPBearer(auto_error=False)
        
        # Security settings
        self.max_file_size = int(os.environ.get("STYLESYNC_MAX_FILE_MB", "10")) * 1024 * 1024
        self.min_edge = int(os.environ.get("STYLESYNC_MIN_EDGE", "256"))
        self.allowed_mime_types = {"image/jpeg", "image/png"}
        self.allowed_extensions = {".jpg", ".jpeg", ".png"}
        
        # CORS settings
        self.allowed_origins = self._get_allowed_origins()
        self.allowed_methods = ["GET", "POST", "OPTIONS"]
        self.allowed_headers = ["*"]
        
        # Feature flags
        self.enforce_https = bool(int(os.environ.get("STYLESYNC_ENFORCE_HTTPS", "1")))
        self.enable_auth = bool(int(os.environ.get("STYLESYNC_ENABLE_AUTH", "1")))
    
    def _get_allowed_origins(self) -> List[str]:
        """Get allowed CORS origins from environment."""
        origins_env = os.environ.get("STYLESYNC_ALLOWED_ORIGINS", "")
        if not origins_env:
            # Default development origins
            return [
                "http://localhost:3000",
                "http://localhost:3002", 
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3002"
            ]
        
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    
    async def authenticate_request(self, credentials: Optional[HTTPAuthorizationCredentials] = Security(HTTPBearer(auto_error=False))) -> Optional[str]:
        """Authenticate request and return API key if valid."""
        if not self.enable_auth:
            return "dev-mode"
        
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        api_key = credentials.credentials
        
        # Validate API key
        if not self.api_key_manager.validate_api_key(api_key):
            logger.warning(f"Invalid API key attempt: {api_key[:8]}...")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
        
        # Check rate limits
        if not self.api_key_manager.check_rate_limit(api_key):
            rate_status = self.api_key_manager.get_rate_limit_status(api_key)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(rate_status["limit"]),
                    "X-RateLimit-Remaining": str(rate_status["remaining"]),
                    "X-RateLimit-Window": str(rate_status["window_seconds"])
                }
            )
        
        return api_key
    
    def validate_image_upload(self, file, content: bytes) -> None:
        """Validate uploaded image file for security and format compliance."""
        
        # Check file size
        if len(content) > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {self.max_file_size // (1024*1024)}MB"
            )
        
        # Check MIME type
        if file.content_type not in self.allowed_mime_types:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported media type. Supported: {', '.join(self.allowed_mime_types)}"
            )
        
        # Check file extension
        if file.filename:
            ext = f".{file.filename.lower().split('.')[-1]}" if '.' in file.filename else ''
            if ext not in self.allowed_extensions:
                raise HTTPException(
                    status_code=415,
                    detail=f"Unsupported file extension. Supported: {', '.join(self.allowed_extensions)}"
                )
        
        # Validate magic bytes
        if not self._validate_image_magic_bytes(content):
            raise HTTPException(
                status_code=400,
                detail="Invalid image file format"
            )
        
        # Check minimum dimensions (basic validation)
        try:
            from PIL import Image
            import io
            
            image = Image.open(io.BytesIO(content))
            width, height = image.size
            
            if min(width, height) < self.min_edge:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image too small. Minimum edge: {self.min_edge}px"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=400,
                detail="Unable to process image file"
            )
    
    def _validate_image_magic_bytes(self, content: bytes) -> bool:
        """Validate image file format using magic bytes."""
        if len(content) < 8:
            return False
        
        # JPEG magic bytes
        if content.startswith(b'\xff\xd8\xff'):
            return True
        
        # PNG magic bytes
        if content.startswith(b'\x89PNG\r\n\x1a\n'):
            return True
        
        return False
    
    def validate_request_size(self, request: Request) -> None:
        """Validate total request size."""
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            if size > self.max_file_size * 2:  # Allow some overhead
                raise HTTPException(
                    status_code=413,
                    detail="Request entity too large"
                )
    
    def validate_https(self, request: Request) -> None:
        """Validate HTTPS requirement in production."""
        if self.enforce_https:
            # Check if request is HTTPS
            scheme = request.url.scheme
            forwarded_proto = request.headers.get("x-forwarded-proto")
            
            if scheme != "https" and forwarded_proto != "https":
                raise HTTPException(
                    status_code=400,
                    detail="HTTPS required"
                )
    
    def get_cors_middleware(self):
        """Get configured CORS middleware."""
        return CORSMiddleware(
            allow_origins=self.allowed_origins,
            allow_credentials=True,
            allow_methods=self.allowed_methods,
            allow_headers=self.allowed_headers,
            expose_headers=[
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining", 
                "X-RateLimit-Window"
            ]
        )
    
    def get_trusted_host_middleware(self):
        """Get trusted host middleware for additional security."""
        allowed_hosts = os.environ.get("STYLESYNC_ALLOWED_HOSTS", "*").split(",")
        return TrustedHostMiddleware(allowed_hosts=allowed_hosts)
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(length)
    
    def hash_data(self, data: str, salt: Optional[str] = None) -> str:
        """Hash data with optional salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        
        combined = f"{salt}{data}".encode('utf-8')
        hash_value = hashlib.sha256(combined).hexdigest()
        
        return f"{salt}:{hash_value}"
    
    def verify_hash(self, data: str, hash_value: str) -> bool:
        """Verify hashed data."""
        try:
            salt, expected_hash = hash_value.split(":", 1)
            actual_hash = self.hash_data(data, salt).split(":", 1)[1]
            return hmac.compare_digest(actual_hash, expected_hash)
        except ValueError:
            return False


class IdempotencyManager:
    """Manages request idempotency keys."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self.storage: Dict[str, Dict[str, any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get_response(self, idempotency_key: str) -> Optional[Dict[str, any]]:
        """Get cached response for idempotency key."""
        if idempotency_key not in self.storage:
            return None
        
        entry = self.storage[idempotency_key]
        
        # Check if expired
        if time.time() - entry['timestamp'] > self.ttl_seconds:
            del self.storage[idempotency_key]
            return None
        
        return entry['response']
    
    def store_response(self, idempotency_key: str, response: Dict[str, any]) -> None:
        """Store response for idempotency key."""
        self.storage[idempotency_key] = {
            'response': response,
            'timestamp': time.time()
        }
        
        # Clean up expired entries periodically
        self._cleanup_expired()
    
    def _cleanup_expired(self) -> None:
        """Remove expired idempotency entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.storage.items()
            if current_time - entry['timestamp'] > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self.storage[key]


# Global security manager instance
security_manager = SecurityManager()
idempotency_manager = IdempotencyManager()
