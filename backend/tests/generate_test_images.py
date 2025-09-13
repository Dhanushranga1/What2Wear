"""
Generate synthetic test images for StyleSync segmentation testing.
"""
import os
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from typing import Tuple


def create_simple_garment_image(
    width: int = 400, 
    height: int = 300,
    garment_color: Tuple[int, int, int] = (120, 80, 160),  # BGR purple
    background_color: Tuple[int, int, int] = (240, 240, 240),  # BGR light gray
    margin: int = 50
) -> np.ndarray:
    """
    Create synthetic image with simple garment shape on contrasting background.
    
    Args:
        width: Image width
        height: Image height  
        garment_color: BGR color for garment
        background_color: BGR color for background
        margin: Margin from edges
        
    Returns:
        BGR image array
    """
    if cv2 is None:
        raise RuntimeError("OpenCV not available for test image generation")
    
    # Create background
    img = np.full((height, width, 3), background_color, dtype=np.uint8)
    
    # Create simple rectangle garment shape
    x1, y1 = margin, margin
    x2, y2 = width - margin, height - margin
    
    cv2.rectangle(img, (x1, y1), (x2, y2), garment_color, -1)
    
    return img


def create_complex_garment_image(
    width: int = 400,
    height: int = 300,
    garment_color: Tuple[int, int, int] = (80, 140, 200),  # BGR orange-ish
    background_color: Tuple[int, int, int] = (50, 50, 50),  # BGR dark gray
    margin: int = 30
) -> np.ndarray:
    """
    Create synthetic image with more complex garment shape.
    
    Args:
        width: Image width
        height: Image height
        garment_color: BGR color for garment  
        background_color: BGR color for background
        margin: Margin from edges
        
    Returns:
        BGR image array
    """
    if cv2 is None:
        raise RuntimeError("OpenCV not available for test image generation")
    
    # Create background
    img = np.full((height, width, 3), background_color, dtype=np.uint8)
    
    # Create complex shape (shirt-like)
    center_x, center_y = width // 2, height // 2
    
    # Main body rectangle
    body_w, body_h = width - 2 * margin, height - 2 * margin
    x1 = center_x - body_w // 2
    y1 = center_y - body_h // 2
    x2 = center_x + body_w // 2
    y2 = center_y + body_h // 2
    
    cv2.rectangle(img, (x1, y1), (x2, y2), garment_color, -1)
    
    # Add sleeves (smaller rectangles)
    sleeve_w, sleeve_h = margin, body_h // 2
    # Left sleeve
    cv2.rectangle(
        img, 
        (x1 - sleeve_w, center_y - sleeve_h // 2), 
        (x1, center_y + sleeve_h // 2), 
        garment_color, -1
    )
    # Right sleeve
    cv2.rectangle(
        img, 
        (x2, center_y - sleeve_h // 2), 
        (x2 + sleeve_w, center_y + sleeve_h // 2), 
        garment_color, -1
    )
    
    return img


def create_challenging_image(
    width: int = 400,
    height: int = 300,
    garment_color: Tuple[int, int, int] = (60, 60, 70),  # BGR dark blue-gray
    background_color: Tuple[int, int, int] = (70, 70, 80),  # BGR similar dark gray
    margin: int = 40
) -> np.ndarray:
    """
    Create challenging image with garment/background having similar colors.
    
    Args:
        width: Image width
        height: Image height
        garment_color: BGR color for garment (close to background)
        background_color: BGR color for background
        margin: Margin from edges
        
    Returns:
        BGR image array
    """
    if cv2 is None:
        raise RuntimeError("OpenCV not available for test image generation")
    
    # Create background
    img = np.full((height, width, 3), background_color, dtype=np.uint8)
    
    # Create circular garment shape
    center = (width // 2, height // 2)
    radius = min(width, height) // 2 - margin
    
    cv2.circle(img, center, radius, garment_color, -1)
    
    # Add some noise to make it more challenging
    noise = np.random.normal(0, 10, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return img


def save_test_images(output_dir: str) -> None:
    """
    Generate and save all test images.
    
    Args:
        output_dir: Directory to save images
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate test images
    simple_img = create_simple_garment_image()
    complex_img = create_complex_garment_image()  
    challenging_img = create_challenging_image()
    
    # Save as JPG
    cv2.imwrite(os.path.join(output_dir, "simple_garment.jpg"), simple_img)
    cv2.imwrite(os.path.join(output_dir, "complex_garment.jpg"), complex_img)
    cv2.imwrite(os.path.join(output_dir, "challenging_garment.jpg"), challenging_img)
    
    print(f"Generated test images in {output_dir}")


if __name__ == "__main__":
    # Generate test images if run directly
    import sys
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "test_images"
    save_test_images(output_dir)
