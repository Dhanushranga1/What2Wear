"""
StyleSync API Schemas
Pydantic models for segmentation and color extraction request/response validation.
"""
from typing import List, Optional, Dict, Union, Any
from pydantic import BaseModel, Field


class Artifacts(BaseModel):
    """Segmentation output artifacts."""
    mask_png_b64: str = Field(
        ..., 
        description="Base64-encoded 8-bit single-channel PNG mask (0=background, 255=garment)"
    )
    item_rgba_png_b64: str = Field(
        ..., 
        description="Base64-encoded 8-bit RGBA PNG with transparent background"
    )
    bbox_xywh: List[int] = Field(
        ..., 
        min_length=4, 
        max_length=4,
        description="Tight bounding box as [x, y, width, height]"
    )


class Debug(BaseModel):
    """Debug information showing processing parameters used."""
    pre_gamma: float = Field(..., description="Gamma correction value applied")
    morph_kernel: int = Field(..., description="Morphological kernel size used")
    post_blur: int = Field(..., description="Median blur kernel size used")


class SegmentResponse(BaseModel):
    """Main segmentation response."""
    engine: str = Field(..., description="Segmentation engine used ('u2netp' or 'grabcut')")
    width: int = Field(..., description="Output image width in pixels")
    height: int = Field(..., description="Output image height in pixels") 
    mask_area_ratio: float = Field(
        ..., 
        description="Ratio of mask area to total image area (0.0-1.0)"
    )
    fallback_used: bool = Field(
        ..., 
        description="Whether fallback to GrabCut was used due to rembg failure"
    )
    artifacts: Artifacts = Field(..., description="Output artifacts")
    debug: Debug = Field(..., description="Debug information")


class HealthResponse(BaseModel):
    """Health check response."""
    ok: bool = Field(True, description="Service health status")
    version: str = Field(..., description="Service version")
    service: str = Field("stylesync-segmentation", description="Service name")


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")


# ============================================================================
# COLOR EXTRACTION SCHEMAS (Phase 2)
# ============================================================================

class ColorEntry(BaseModel):
    """Single color in a palette with dominance ratio."""
    hex: str = Field(
        ..., 
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color code in format #RRGGBB"
    )
    ratio: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Dominance ratio (0.0-1.0) of this color in the garment"
    )


class BaseColorInfo(BaseModel):
    """Information about the selected base color."""
    hex: str = Field(
        ..., 
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color code of the base color"
    )
    cluster_index: int = Field(
        ..., 
        ge=0,
        description="Index of this color in the dominance-ordered palette"
    )
    score_breakdown: Dict[str, float] = Field(
        ...,
        description="Scoring components: dominance, neutral_penalty, cohesion_bonus, final_score"
    )


class ColorExtractRequestDirect(BaseModel):
    """Direct mode request with pre-segmented image and mask."""
    mask_png_b64: str = Field(
        ...,
        description="Base64-encoded single-channel PNG mask (0=background, 255=garment)"
    )
    item_rgba_png_b64: Optional[str] = Field(
        None,
        description="Base64-encoded RGBA PNG (if provided, alpha cross-checks mask)"
    )
    item_png_b64: Optional[str] = Field(
        None,
        description="Base64-encoded RGB PNG (requires mask_png_b64)"
    )


class ColorArtifacts(BaseModel):
    """Color extraction output artifacts."""
    swatch_png_b64: Optional[str] = Field(
        None,
        description="Base64-encoded PNG showing color palette strip"
    )
    mask_area_ratio: float = Field(
        ...,
        description="Ratio of garment pixels to total image area"
    )
    harmony_analysis: Optional[Dict[str, Union[str, float]]] = Field(
        None,
        description="Optional color harmony analysis for the palette"
    )


class ColorDebug(BaseModel):
    """Debug information for color extraction."""
    gamma: float = Field(..., description="Gamma correction applied")
    erode_for_sampling: int = Field(..., description="Mask erosion pixels for sampling")
    filters: Dict[str, float] = Field(
        ...,
        description="HSV filter thresholds: shadow_v_lt, specular_s_lt, specular_v_gt, min_saturation"
    )
    neutral_thresholds: Dict[str, float] = Field(
        ...,
        description="Neutral penalty parameters: v_low, v_high, s_low, penalty_weight"
    )
    cohesion: Dict[str, Union[bool, float]] = Field(
        ...,
        description="Spatial cohesion parameters: enabled, weight"
    )
    processing_mode: str = Field(
        ...,
        description="Processing mode used: 'direct' or 'oneshot'"
    )


class ColorExtractResponse(BaseModel):
    """Main color extraction response."""
    width: int = Field(..., description="Processed image width in pixels")
    height: int = Field(..., description="Processed image height in pixels")
    k: int = Field(..., description="Number of color clusters requested")
    sampled_pixels: int = Field(
        ..., 
        description="Number of pixels sampled after filtering"
    )
    palette: List[ColorEntry] = Field(
        ...,
        description="Color palette ordered by dominance (most to least dominant)"
    )
    base_color: BaseColorInfo = Field(
        ...,
        description="Selected base color with scoring details"
    )
    debug: ColorDebug = Field(..., description="Debug information and parameters")
    artifacts: Optional[ColorArtifacts] = Field(
        None,
        description="Optional artifacts like swatch images and analysis"
    )


# ============================================================================
# COLOR SUGGESTION SCHEMAS (Phase 3)
# ============================================================================

class ColorSuggestionRequestDirect(BaseModel):
    """Direct mode request with base color hex."""
    base_hex: str = Field(
        ...,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Base color in format #RRGGBB"
    )
    palette: Optional[List[ColorEntry]] = Field(
        None,
        description="Optional Phase-2 palette for reference"
    )


class ColorSuggestionHLS(BaseModel):
    """HLS color representation for suggestions."""
    h: float = Field(..., ge=0.0, lt=1.0, description="Hue [0, 1)")
    l: float = Field(..., ge=0.0, le=1.0, description="Lightness [0, 1]")
    s: float = Field(..., ge=0.0, le=1.0, description="Saturation [0, 1]")


class ColorSuggestion(BaseModel):
    """Single color suggestion with metadata."""
    hex: str = Field(
        ...,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Suggestion color in format #RRGGBB"
    )
    category: str = Field(
        ...,
        description="Harmony category: complementary, analogous, triadic, neutral"
    )
    role_target: str = Field(
        ...,
        description="Target garment role for this suggestion"
    )
    hls: ColorSuggestionHLS = Field(
        ...,
        description="Final HLS values after all constraints applied"
    )
    rationale: List[str] = Field(
        ...,
        description="Token list explaining decisions made for this suggestion"
    )


class SuggestionMeta(BaseModel):
    """Metadata about the suggestion request and base color."""
    base_hex: str = Field(..., description="Original base color")
    base_hls: ColorSuggestionHLS = Field(..., description="Base color in HLS")
    source_role: str = Field(..., description="Source garment role")
    target_role: str = Field(..., description="Target garment role")
    intent: str = Field(..., description="Style intent: safe, classic, bold")
    season: str = Field(..., description="Seasonal bias: all, spring_summer, autumn_winter")


class SuggestionPolicy(BaseModel):
    """Policy constants used for suggestion generation."""
    delta_l_min: float = Field(..., description="Minimum lightness contrast")
    role_l_bands: Dict[str, List[float]] = Field(..., description="Lightness bands by role")
    role_s_caps: Dict[str, Dict[str, float]] = Field(..., description="Saturation caps by role and intent")
    analogous_min_sep_degrees: float = Field(..., description="Minimum analogous hue separation")
    seasonal_l_nudge: float = Field(..., description="Seasonal lightness adjustment")
    hyper_sat_threshold: float = Field(..., description="Hyper-saturation detection threshold")
    degenerate_s_threshold: float = Field(..., description="Degenerate base saturation threshold")
    neutral_pool: Dict[str, Any] = Field(..., description="Neutral color pool metadata")


class SuggestionArtifacts(BaseModel):
    """Artifacts generated for color suggestions."""
    swatch_png_b64: Optional[str] = Field(
        None,
        description="Base64-encoded PNG swatch grouped by category"
    )
    swatch_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Metadata about swatch generation parameters"
    )


class SuggestionDebug(BaseModel):
    """Debug information for suggestion generation."""
    processing_notes: List[str] = Field(..., description="Processing decisions and notes")
    timing_ms: Dict[str, float] = Field(..., description="Timing breakdown in milliseconds")
    category_counts: Dict[str, int] = Field(..., description="Number of suggestions per category")


class ColorSuggestionResponse(BaseModel):
    """Main color suggestion response."""
    meta: SuggestionMeta = Field(..., description="Request metadata and base color info")
    suggestions: Dict[str, List[ColorSuggestion]] = Field(
        ...,
        description="Color suggestions grouped by harmony category"
    )
    policy: SuggestionPolicy = Field(..., description="Policy constants used")
    artifacts: SuggestionArtifacts = Field(..., description="Generated artifacts")
    debug: SuggestionDebug = Field(..., description="Debug information")
