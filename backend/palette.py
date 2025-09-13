"""
Color palette extraction for garment images
"""
from PIL import Image
import numpy as np
import requests
from io import BytesIO
from sklearn.cluster import KMeans
from typing import List

# Color bin definitions
BIN_RING = ["red", "orange", "yellow", "green", "teal", "blue", "purple", "pink"]  # 8 bins on hue ring
ALL_BINS = BIN_RING + ["brown", "neutral"]


def hue_to_bin(h_deg: float) -> str:
    """
    Map hue degree (0-360) to nearest color bin
    """
    # Normalize to 0-360 range and map to 8-bin ring
    idx = int((h_deg % 360) / 360 * len(BIN_RING))
    return BIN_RING[idx]


def rgb_to_hsv(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert RGB arrays to HSV arrays
    """
    rgb = np.stack([r, g, b], axis=-1)
    cmax = np.max(rgb, axis=-1)
    cmin = np.min(rgb, axis=-1)
    diff = cmax - cmin

    # Hue calculation
    hue = np.zeros_like(cmax)
    mask = diff != 0
    
    # Red is max
    rmax = (cmax == r) & mask
    hue[rmax] = (60 * ((g[rmax] - b[rmax]) / diff[rmax]) + 360) % 360
    
    # Green is max
    gmax = (cmax == g) & mask
    hue[gmax] = (60 * ((b[gmax] - r[gmax]) / diff[gmax]) + 120) % 360
    
    # Blue is max
    bmax = (cmax == b) & mask
    hue[bmax] = (60 * ((r[bmax] - g[bmax]) / diff[bmax]) + 240) % 360

    # Saturation calculation
    sat = np.zeros_like(cmax)
    sat[cmax != 0] = diff[cmax != 0] / cmax[cmax != 0]
    
    # Value is just the max
    val = cmax

    return hue, sat, val


def extract_color_bins(image_url: str) -> List[str]:
    """
    Extract color bins from an image URL
    
    Args:
        image_url: URL to fetch the image from
        
    Returns:
        List of color bin names
        
    Raises:
        Exception: If image cannot be processed
    """
    try:
        # 1) Fetch image with timeout
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        # 2) Open and downscale image
        image = Image.open(BytesIO(response.content)).convert("RGB")
        image.thumbnail((256, 256), Image.LANCZOS)

        # Convert to numpy array
        arr = np.asarray(image, dtype=np.float32) / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

        # 3) Convert to HSV
        hue, sat, val = rgb_to_hsv(r, g, b)

        # 4) Filter near-neutral pixels
        # Remove pixels with low saturation or extreme brightness
        keep_mask = (sat > 0.2) & (val > 0.2) & (val < 0.98)
        hue_values = hue[keep_mask]

        # If too few colorful pixels, return neutral
        if hue_values.shape[0] < 100:
            return ["neutral"]

        # 5) Cluster hues
        # Use fewer clusters for simpler palettes
        k = min(3, max(1, hue_values.shape[0] // 100))
        
        # Reshape for sklearn
        hue_reshaped = hue_values.reshape(-1, 1)
        
        kmeans = KMeans(n_clusters=k, n_init=5, random_state=42)
        kmeans.fit(hue_reshaped)
        
        # Get cluster centers and sort them
        centers = sorted(float(center[0]) for center in kmeans.cluster_centers_)

        # 6) Map centers to color bins
        bins = []
        for center_hue in centers:
            bin_name = hue_to_bin(center_hue)
            if bin_name not in bins:  # Avoid duplicates
                bins.append(bin_name)

        # 7) Always include neutral for better matching
        if "neutral" not in bins:
            bins.append("neutral")

        return bins

    except Exception as e:
        # Log the specific error for debugging
        print(f"Error extracting color bins: {str(e)}")
        raise Exception("Could not extract color bins from image")
