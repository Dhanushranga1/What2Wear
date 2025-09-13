"""
GrabCut Segmentation Engine
Fallback segmentation using OpenCV GrabCut algorithm.
"""
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


class GrabCutEngine:
    """GrabCut segmentation engine using OpenCV."""
    
    def __init__(self):
        """Initialize GrabCut engine."""
        if cv2 is None:
            raise RuntimeError("OpenCV not available. Install with: pip install opencv-python")
    
    def segment(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Segment image using GrabCut algorithm with central rectangle initialization.
        
        Args:
            image_bgr: Input image in BGR format (uint8)
            
        Returns:
            Binary mask (uint8, 0 or 255)
            
        Raises:
            RuntimeError: If segmentation fails
        """
        if cv2 is None:
            raise RuntimeError("OpenCV not available")
        
        try:
            height, width = image_bgr.shape[:2]
            
            # Initialize with central 70% rectangle
            margin_w = int(0.15 * width)
            margin_h = int(0.15 * height)
            rect_x = margin_w
            rect_y = margin_h
            rect_w = width - 2 * margin_w
            rect_h = height - 2 * margin_h
            
            # Ensure rectangle is valid
            if rect_w <= 0 or rect_h <= 0:
                raise RuntimeError("Image too small for GrabCut rectangle initialization")
            
            rect = (rect_x, rect_y, rect_w, rect_h)
            
            # Initialize GrabCut mask and models
            mask = np.zeros((height, width), np.uint8)
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)
            
            # Run GrabCut algorithm (5 iterations)
            cv2.grabCut(
                image_bgr, mask, rect, bgd_model, fgd_model, 
                5, cv2.GC_INIT_WITH_RECT
            )
            
            # Extract foreground pixels
            fg_mask = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
            binary_mask = np.where(fg_mask, 255, 0).astype("uint8")
            
            return binary_mask
            
        except Exception as e:
            raise RuntimeError(f"GrabCut segmentation failed: {str(e)}")
    
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
_grabcut_engine = None


def get_grabcut_engine() -> GrabCutEngine:
    """Get or create global GrabCut engine instance."""
    global _grabcut_engine
    if _grabcut_engine is None:
        _grabcut_engine = GrabCutEngine()
    return _grabcut_engine
