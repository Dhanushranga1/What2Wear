"""
Generate synthetic test images for Phase 2 color extraction testing.

Creates controlled test cases with known color distributions:
- two_blocks.png: 50/50 blue/camel split 
- stripes.png: Alternating teal/white vertical stripes
- logo_on_shirt.png: Navy shirt with small white logo
"""

import cv2
import numpy as np
import os
from pathlib import Path

def create_two_blocks():
    """Create 256x256 image: left half blue (#1F4E79), right half camel (#D3B58F)"""
    img = np.zeros((256, 256, 3), dtype=np.uint8)
    
    # Left half: Blue
    blue_bgr = (0x79, 0x4E, 0x1F)  # BGR format for OpenCV
    img[:, :128] = blue_bgr
    
    # Right half: Camel  
    camel_bgr = (0x8F, 0xB5, 0xD3)  # BGR format for OpenCV
    img[:, 128:] = camel_bgr
    
    return img

def create_stripes():
    """Create 256x256 image: alternating teal/white vertical stripes (16px each)"""
    img = np.zeros((256, 256, 3), dtype=np.uint8)
    
    # Teal and white colors
    teal_bgr = (0x60, 0x75, 0x2D)  # #2D7560 in BGR
    white_bgr = (255, 255, 255)
    
    stripe_width = 16
    for x in range(0, 256, stripe_width * 2):
        # Teal stripe
        img[:, x:min(x + stripe_width, 256)] = teal_bgr
        # White stripe (next stripe_width pixels)
        if x + stripe_width < 256:
            img[:, x + stripe_width:min(x + 2 * stripe_width, 256)] = white_bgr
    
    return img

def create_logo_on_shirt():
    """Create 256x256 navy shirt with small white logo in center"""
    img = np.zeros((256, 256, 3), dtype=np.uint8)
    
    # Navy background
    navy_bgr = (0x43, 0x2A, 0x0A)  # #0A2A43 in BGR
    img[:, :] = navy_bgr
    
    # Small white logo (32x32 square in center)
    white_bgr = (255, 255, 255)
    center_x, center_y = 128, 128
    logo_size = 32
    x1 = center_x - logo_size // 2
    x2 = center_x + logo_size // 2
    y1 = center_y - logo_size // 2  
    y2 = center_y + logo_size // 2
    
    img[y1:y2, x1:x2] = white_bgr
    
    return img

def create_full_mask(img_shape):
    """Create a full white mask for entire image"""
    h, w = img_shape[:2]
    mask = np.full((h, w), 255, dtype=np.uint8)
    return mask

def save_test_assets(output_dir):
    """Generate and save all test assets"""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"Generating synthetic test assets in {output_dir}")
    
    # Generate images
    test_cases = {
        "two_blocks.png": create_two_blocks(),
        "stripes.png": create_stripes(), 
        "logo_on_shirt.png": create_logo_on_shirt()
    }
    
    for filename, img in test_cases.items():
        # Save image
        img_path = output_dir / filename
        cv2.imwrite(str(img_path), img)
        print(f"Created {filename}: {img.shape}")
        
        # Save corresponding mask
        mask = create_full_mask(img.shape)
        mask_filename = filename.replace('.png', '_mask.png')
        mask_path = output_dir / mask_filename
        cv2.imwrite(str(mask_path), mask)
        print(f"Created {mask_filename}: {mask.shape}")
        
        # Verify expected colors for validation
        if filename == "two_blocks.png":
            print(f"  Expected: ~50% blue (#1F4E79), ~50% camel (#D3B58F)")
        elif filename == "stripes.png":
            print(f"  Expected: ~50% teal (#2D7560), ~50% white (#FFFFFF)")
        elif filename == "logo_on_shirt.png":
            logo_area = 32 * 32
            total_area = 256 * 256
            logo_ratio = logo_area / total_area
            print(f"  Expected: ~{(1-logo_ratio)*100:.1f}% navy (#0A2A43), ~{logo_ratio*100:.1f}% white (#FFFFFF)")

if __name__ == "__main__":
    # Use the existing tests/assets directory
    assets_dir = Path(__file__).parent / "assets"
    save_test_assets(assets_dir)
    print("\nSynthetic test assets generated successfully!")
    print("Use these for:")
    print("- Unit testing color extraction algorithms")
    print("- Validating base color selection logic") 
    print("- API integration testing with known ground truth")
