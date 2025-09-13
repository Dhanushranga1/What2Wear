"""
StyleSync Fingerprinting Utilities
Handles content deduplication and cache key generation.
"""
import hashlib
import io
from typing import Dict, Any, Tuple
from PIL import Image
import numpy as np


def compute_sha256(image_bytes: bytes) -> str:
    """
    Compute SHA-256 hash of normalized image bytes.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        SHA-256 hash as hex string
    """
    return hashlib.sha256(image_bytes).hexdigest()


def compute_perceptual_hash(image: Image.Image, hash_size: int = 8) -> str:
    """
    Compute perceptual hash (pHash) for near-duplicate detection.
    
    Args:
        image: PIL Image object
        hash_size: Size of the hash (8x8 = 64-bit)
        
    Returns:
        Perceptual hash as hex string
    """
    # Convert to grayscale and resize
    gray = image.convert('L').resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    
    # Convert to numpy array
    pixels = np.array(gray).flatten()
    
    # Compute DCT (simplified version using mean comparison)
    mean = pixels.mean()
    hash_bits = (pixels > mean).astype(int)
    
    # Convert to hex string
    hash_value = 0
    for bit in hash_bits:
        hash_value = (hash_value << 1) | bit
    
    return f"{hash_value:016x}"


def normalize_image_for_hashing(image_bytes: bytes, max_edge: int = 768) -> Tuple[bytes, Dict[str, Any]]:
    """
    Normalize image for consistent hashing (resize, orientation fix).
    
    Args:
        image_bytes: Raw image bytes
        max_edge: Maximum edge size for normalization
        
    Returns:
        Tuple of (normalized_bytes, metadata)
    """
    try:
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Apply EXIF orientation
        if hasattr(image, '_getexif') and image._getexif() is not None:
            from PIL.ExifTags import ORIENTATION
            exif = image._getexif()
            orientation = exif.get(ORIENTATION)
            if orientation:
                if orientation == 3:
                    image = image.rotate(180, expand=True)
                elif orientation == 6:
                    image = image.rotate(270, expand=True)
                elif orientation == 8:
                    image = image.rotate(90, expand=True)
        
        # Resize to max_edge for consistent hashing
        original_width, original_height = image.size
        if max(original_width, original_height) > max_edge:
            if original_width > original_height:
                new_width = max_edge
                new_height = int(original_height * max_edge / original_width)
            else:
                new_height = max_edge
                new_width = int(original_width * max_edge / original_height)
            
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save normalized image to bytes
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=95)
        normalized_bytes = output.getvalue()
        
        metadata = {
            'original_size': (original_width, original_height),
            'normalized_size': image.size,
            'format': image.format,
            'mode': image.mode
        }
        
        return normalized_bytes, metadata
        
    except Exception as e:
        raise ValueError(f"Failed to normalize image: {str(e)}")


def generate_content_fingerprint(image_bytes: bytes, max_edge: int = 768) -> Dict[str, Any]:
    """
    Generate complete content fingerprint for image.
    
    Args:
        image_bytes: Raw image bytes
        max_edge: Maximum edge for normalization
        
    Returns:
        Dictionary containing sha256, phash, and metadata
    """
    # Normalize image for consistent hashing
    normalized_bytes, metadata = normalize_image_for_hashing(image_bytes, max_edge)
    
    # Compute hashes
    sha256 = compute_sha256(normalized_bytes)
    
    # Load normalized image for perceptual hashing
    normalized_image = Image.open(io.BytesIO(normalized_bytes))
    phash = compute_perceptual_hash(normalized_image)
    
    return {
        'sha256': sha256,
        'phash': phash,
        'metadata': metadata,
        'normalized_size_bytes': len(normalized_bytes)
    }


def generate_cache_key_digest(params: Dict[str, Any]) -> str:
    """
    Generate deterministic digest for parameter combinations.
    
    Args:
        params: Dictionary of parameters
        
    Returns:
        MD5 digest of sorted parameters
    """
    # Sort parameters deterministically
    sorted_items = sorted(params.items())
    param_string = str(sorted_items)
    
    return hashlib.md5(param_string.encode()).hexdigest()


def generate_composite_cache_key(prefix: str, sha256: str, params_digest: str, policy_version: str = "1.0.0") -> str:
    """
    Generate composite cache key for multi-layer caching.
    
    Args:
        prefix: Cache layer prefix (seg, col, adv)
        sha256: Content SHA-256 hash
        params_digest: Parameters digest
        policy_version: Policy version for invalidation
        
    Returns:
        Composite cache key
    """
    return f"{prefix}:{sha256[:12]}:{params_digest[:8]}:{policy_version}"


class FingerprintManager:
    """Manager class for fingerprinting operations."""
    
    def __init__(self, policy_version: str = "1.0.0"):
        self.policy_version = policy_version
    
    def process_image(self, image_bytes: bytes, max_edge: int = 768) -> Dict[str, Any]:
        """
        Process image and generate complete fingerprint.
        
        Args:
            image_bytes: Raw image bytes
            max_edge: Maximum edge for normalization
            
        Returns:
            Complete fingerprint data
        """
        return generate_content_fingerprint(image_bytes, max_edge)
    
    def get_segmentation_cache_key(self, sha256: str, gamma: float, max_edge: int, engine: str) -> str:
        """Generate segmentation cache key."""
        params = {
            'gamma': gamma,
            'max_edge': max_edge, 
            'engine': engine
        }
        digest = generate_cache_key_digest(params)
        return generate_composite_cache_key('seg', sha256, digest, self.policy_version)
    
    def get_extraction_cache_key(self, sha256: str, gamma: float, k: int, filters: Dict[str, Any]) -> str:
        """Generate color extraction cache key."""
        params = {
            'gamma': gamma,
            'k': k,
            **filters
        }
        digest = generate_cache_key_digest(params)
        return generate_composite_cache_key('col', sha256, digest, self.policy_version)
    
    def get_advice_cache_key(self, sha256: str, all_params: Dict[str, Any]) -> str:
        """Generate advice cache key."""
        digest = generate_cache_key_digest(all_params)
        return generate_composite_cache_key('adv', sha256, digest, self.policy_version)
