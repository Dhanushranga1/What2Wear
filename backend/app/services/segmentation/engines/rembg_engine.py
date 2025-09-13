"""
rembg Segmentation Engine
Primary segmentation using rembg U²-Netp model.
"""
import numpy as np
from typing import Optional

try:
    from rembg import remove, new_session
except ImportError:
    # Handle case where rembg is not installed yet
    remove = None
    new_session = None

from app.config import config


class RembgEngine:
    """U²-Netp segmentation engine using rembg."""
    
    def __init__(self):
        """Initialize rembg session with U²-Netp model."""
        self._session = None
        self._initialize_session()
    
    def _initialize_session(self) -> None:
        """Initialize the rembg session lazily."""
        if new_session is None:
            raise RuntimeError("rembg not available. Install with: pip install rembg")
        
        try:
            # Create session with U²-Netp model (fast, CPU-friendly)
            self._session = new_session("u2net")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize rembg session: {str(e)}")
    
    def segment(self, image_rgb: np.ndarray) -> np.ndarray:
        """
        Segment image using rembg U²-Netp model.
        
        Args:
            image_rgb: Input image in RGB format (uint8)
            
        Returns:
            Binary mask (uint8, 0 or 255)
            
        Raises:
            RuntimeError: If segmentation fails
        """
        if self._session is None:
            self._initialize_session()
        
        if remove is None:
            raise RuntimeError("rembg not available")
        
        try:
            # rembg expects RGB input and returns RGBA output
            result_rgba = remove(image_rgb, session=self._session)
            
            # Extract alpha channel
            if len(result_rgba.shape) == 3 and result_rgba.shape[2] == 4:
                alpha = result_rgba[:, :, 3]
            else:
                raise RuntimeError("rembg output format unexpected")
            
            # Convert to binary mask (threshold alpha > 10)
            binary_mask = np.where(alpha > 10, 255, 0).astype("uint8")
            
            return binary_mask
            
        except Exception as e:
            raise RuntimeError(f"rembg segmentation failed: {str(e)}")
    
    def get_mask_area_ratio(self, mask: np.ndarray) -> float:
        """
        Calculate the ratio of mask area to total image area.
        
        Args:
            mask: Binary mask
            
        Returns:
            Ratio between 0.0 and 1.0
        """
        total_pixels = mask.shape[0] * mask.shape[1]
        mask_pixels = np.count_nonzero(mask)
        return mask_pixels / total_pixels if total_pixels > 0 else 0.0


# Global instance for reuse across requests
_rembg_engine: Optional[RembgEngine] = None


def get_rembg_engine() -> RembgEngine:
    """Get or create global rembg engine instance."""
    global _rembg_engine
    if _rembg_engine is None:
        _rembg_engine = RembgEngine()
    return _rembg_engine
