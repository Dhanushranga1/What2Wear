"""
StyleSync Imaging Utilities
Handles image I/O, validation, preprocessing, and safety checks.
"""
import io
import mimetypes
from typing import Tuple

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.config import config


def validate_file_upload(file: UploadFile) -> None:
    """
    Validate uploaded file for security and format compliance.
    
    Args:
        file: FastAPI UploadFile object
        
    Raises:
        HTTPException: 400 for invalid files, 415 for unsupported formats
    """
    # Check file size (file.size might be None for some clients)
    if hasattr(file, 'size') and file.size and file.size > config.MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Maximum size: {config.MAX_FILE_MB}MB"
        )
    
    # Validate MIME type
    if file.content_type not in config.SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type. Supported: {', '.join(config.SUPPORTED_MIME_TYPES)}"
        )
    
    # Validate file extension
    if file.filename:
        ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        if f".{ext}" not in config.SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file extension. Supported: {', '.join(config.SUPPORTED_EXTENSIONS)}"
            )


def validate_magic_bytes(file_bytes: bytes) -> str:
    """
    Validate file magic bytes to ensure it's actually an image.
    
    Args:
        file_bytes: Raw file bytes
        
    Returns:
        Detected MIME type
        
    Raises:
        HTTPException: 400 for invalid/corrupt files
    """
    if len(file_bytes) < 8:
        raise HTTPException(status_code=400, detail="File too small or corrupt")
    
    # Check magic bytes for common image formats
    if file_bytes.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif file_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    else:
        raise HTTPException(
            status_code=400, 
            detail="Invalid image file. Magic bytes don't match supported formats."
        )


async def read_image(file: UploadFile) -> np.ndarray:
    """
    Safely read and decode image file to BGR numpy array.
    
    Args:
        file: FastAPI UploadFile object
        
    Returns:
        numpy array in BGR format (OpenCV standard)
        
    Raises:
        HTTPException: 400 for decode errors or invalid dimensions
    """
    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    # Validate file size after reading
    if len(file_bytes) > config.MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {config.MAX_FILE_MB}MB"
        )
    
    # Validate magic bytes
    validate_magic_bytes(file_bytes)
    
    try:
        # Decode using PIL for safety, then convert to OpenCV format
        pil_image = Image.open(io.BytesIO(file_bytes))
        
        # Convert to RGB if necessary
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Convert PIL to numpy array (RGB)
        rgb_array = np.array(pil_image)
        
        # Convert RGB to BGR for OpenCV
        bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
        
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to decode image: {str(e)}"
        )
    
    # Validate dimensions
    height, width = bgr_array.shape[:2]
    if width < config.MIN_EDGE or height < config.MIN_EDGE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too small. Minimum dimension: {config.MIN_EDGE}px"
        )
    
    return bgr_array


def resize_long_edge(img_bgr: np.ndarray, max_edge: int = None) -> np.ndarray:
    """
    Resize image so the longest edge is at most max_edge pixels.
    
    Args:
        img_bgr: Input image in BGR format
        max_edge: Maximum edge size (default from config)
        
    Returns:
        Resized image in BGR format
    """
    if max_edge is None:
        max_edge = config.MAX_EDGE
    
    height, width = img_bgr.shape[:2]
    current_max = max(height, width)
    
    if current_max <= max_edge:
        return img_bgr
    
    # Calculate new dimensions
    scale = max_edge / current_max
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    # Use INTER_AREA for downscaling (better quality)
    resized = cv2.resize(img_bgr, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    return resized


def gamma_correct(img_bgr: np.ndarray, gamma: float = None) -> np.ndarray:
    """
    Apply gamma correction to lift shadows and improve segmentation.
    
    Args:
        img_bgr: Input image in BGR format
        gamma: Gamma value (default from config)
        
    Returns:
        Gamma-corrected image
    """
    if gamma is None:
        gamma = config.DEFAULT_GAMMA
    
    # Build lookup table for gamma correction
    inv_gamma = 1.0 / gamma
    lut = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)], dtype="uint8")
    
    # Apply gamma correction using LUT
    return cv2.LUT(img_bgr, lut)


def maybe_grayworld_wb(img_bgr: np.ndarray) -> np.ndarray:
    """
    Optional gray-world white balance correction.
    Currently returns input unchanged. Can be implemented with opencv-contrib.
    
    Args:
        img_bgr: Input image in BGR format
        
    Returns:
        White-balanced image (currently unchanged)
    """
    # TODO: Implement with opencv-contrib if needed
    # For Phase 1, we skip this advanced feature
    return img_bgr


def get_image_dimensions(img_bgr: np.ndarray) -> Tuple[int, int]:
    """
    Get image width and height.
    
    Args:
        img_bgr: Input image
        
    Returns:
        Tuple of (width, height)
    """
    height, width = img_bgr.shape[:2]
    return width, height
