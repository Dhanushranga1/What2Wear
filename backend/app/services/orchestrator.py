"""
StyleSync Unified Orchestrator
Implements the /v1/advice endpoint that chains Phase 1-3 together.
"""
import asyncio
import io
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import HTTPException, UploadFile
from PIL import Image
import logging

from app.services.fingerprint import FingerprintManager
from app.services.cache import MultiLayerCache
from app.config import config

# Import existing phase services (these will be imported at runtime)
# from app.services.segmentation import run_segmentation
# from app.services.colors import extraction, suggest_api

logger = logging.getLogger(__name__)


class OrchestrationResult:
    """Result container for orchestration operations."""
    
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.timings = {}
        self.cache_hits = {}
        self.from_cache = False
        self.degraded = False
        self.processing_notes = []
        
        # Phase results
        self.input_fingerprint = {}
        self.segmentation_result = None
        self.extraction_result = None
        self.suggestions_result = None
        
        # Final consolidated response
        self.response = {}


class AdviceOrchestrator:
    """Main orchestrator for unified advice endpoint."""
    
    def __init__(self, redis_url: Optional[str] = None, policy_version: str = "1.0.0"):
        self.fingerprint_manager = FingerprintManager(policy_version)
        self.cache = MultiLayerCache(redis_url)
        self.policy_version = policy_version
        
        # Timeouts (milliseconds)
        self.timeouts = {
            'segmentation': 1200,
            'extraction': 300,
            'harmony': 100,
            'total': 2500
        }
    
    async def process_advice_request(
        self,
        input_mode: str,
        file: Optional[UploadFile] = None,
        asset_url: Optional[str] = None,
        phase2_response: Optional[Dict[str, Any]] = None,
        base_hex: Optional[str] = None,
        mask_png_b64: Optional[str] = None,
        item_rgba_png_b64: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        cache_ok: bool = True,
        force_recompute: bool = False,
        **params
    ) -> Dict[str, Any]:
        """
        Process unified advice request through all phases.
        
        Args:
            input_mode: "multipart", "by_url", or "artifacts_direct"
            file: Uploaded file (multipart mode)
            asset_url: Pre-uploaded asset URL (by_url mode)
            phase2_response: Phase 2 response (passthrough mode) 
            base_hex: Base color hex (direct mode)
            mask_png_b64: Mask image base64 (artifacts mode)
            item_rgba_png_b64: Item RGBA base64 (artifacts mode)
            idempotency_key: Client idempotency key
            cache_ok: Allow cache usage
            force_recompute: Force recomputation
            **params: All other parameters for phases 1-3
            
        Returns:
            Consolidated advice response
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())
        result = OrchestrationResult(request_id)
        
        try:
            logger.info(f"[{request_id}] Starting advice orchestration", extra={
                'request_id': request_id,
                'input_mode': input_mode,
                'cache_ok': cache_ok,
                'force_recompute': force_recompute
            })
            
            # Check idempotency
            if idempotency_key and cache_ok and not force_recompute:
                cached_response = self.cache.get_idempotency(idempotency_key)
                if cached_response:
                    logger.info(f"[{request_id}] Returning idempotent response")
                    return cached_response
            
            # Step 1: Validate inputs and prepare image
            image_bytes = None
            if input_mode == "multipart":
                if not file:
                    raise HTTPException(status_code=400, detail="File required for multipart mode")
                image_bytes = await file.read()
            elif input_mode == "by_url":
                if not asset_url:
                    raise HTTPException(status_code=400, detail="asset_url required for by_url mode")
                # TODO: Download from asset_url
                raise HTTPException(status_code=501, detail="by_url mode not yet implemented")
            elif input_mode == "artifacts_direct":
                if base_hex:
                    # Skip to Phase 3 directly
                    return await self._process_direct_harmony_mode(result, base_hex, **params)
                elif mask_png_b64 and item_rgba_png_b64:
                    # Skip to Phase 2
                    return await self._process_artifacts_mode(result, mask_png_b64, item_rgba_png_b64, **params)
                else:
                    raise HTTPException(status_code=400, detail="Invalid artifacts_direct mode parameters")
            else:
                raise HTTPException(status_code=400, detail=f"Invalid input_mode: {input_mode}")
            
            # Step 2: Generate fingerprint
            if image_bytes:
                result.input_fingerprint = self.fingerprint_manager.process_image(
                    image_bytes, 
                    params.get('max_edge', config.MAX_EDGE)
                )
                
                logger.info(f"[{request_id}] Generated fingerprint", extra={
                    'sha256': result.input_fingerprint['sha256'][:12],
                    'phash': result.input_fingerprint['phash'][:12]
                })
            
            # Step 3: Check L1 content dedup cache
            if cache_ok and not force_recompute and image_bytes:
                l1_key = f"{result.input_fingerprint['sha256']}:{self._get_params_hash(**params)}"
                cached_advice = self.cache.get_l1_content_dedup(l1_key)
                if cached_advice:
                    logger.info(f"[{request_id}] L1 cache hit")
                    cached_advice['from_cache'] = True
                    cached_advice['cache_keys'] = {'l1': l1_key}
                    return cached_advice
            
            # Step 4: Execute phase pipeline
            await self._execute_phase_pipeline(result, image_bytes, **params)
            
            # Step 5: Build consolidated response
            response = self._build_consolidated_response(result, **params)
            
            # Step 6: Cache results
            if cache_ok and image_bytes:
                l1_key = f"{result.input_fingerprint['sha256']}:{self._get_params_hash(**params)}"
                self.cache.set_l1_content_dedup(l1_key, response)
                
                if idempotency_key:
                    self.cache.set_idempotency(idempotency_key, response)
            
            total_time = (time.time() - start_time) * 1000
            response['debug']['total_ms'] = round(total_time, 2)
            
            logger.info(f"[{request_id}] Orchestration complete", extra={
                'total_ms': total_time,
                'degraded': result.degraded
            })
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{request_id}] Orchestration failed", extra={
                'error': str(e),
                'input_mode': input_mode
            })
            raise HTTPException(status_code=500, detail="Internal orchestration error")
    
    async def _execute_phase_pipeline(self, result: OrchestrationResult, image_bytes: bytes, **params):
        """Execute the Phase 1 -> Phase 2 -> Phase 3 pipeline."""
        
        # Phase 1: Segmentation
        segmentation_start = time.time()
        result.segmentation_result = await self._run_phase1_segmentation(
            result, image_bytes, **params
        )
        result.timings['segmentation_ms'] = round((time.time() - segmentation_start) * 1000, 2)
        
        # Phase 2: Color Extraction
        extraction_start = time.time()
        result.extraction_result = await self._run_phase2_extraction(
            result, **params
        )
        result.timings['extraction_ms'] = round((time.time() - extraction_start) * 1000, 2)
        
        # Phase 3: Harmony & Suggestions
        harmony_start = time.time()
        result.suggestions_result = await self._run_phase3_harmony(
            result, **params
        )
        result.timings['harmony_ms'] = round((time.time() - harmony_start) * 1000, 2)
    
    async def _run_phase1_segmentation(self, result: OrchestrationResult, image_bytes: bytes, **params) -> Dict[str, Any]:
        """Run Phase 1 segmentation with caching."""
        
        # Check L2 cache
        cache_key = self.fingerprint_manager.get_segmentation_cache_key(
            result.input_fingerprint['sha256'],
            params.get('gamma', config.DEFAULT_GAMMA),
            params.get('max_edge', config.MAX_EDGE),
            params.get('phase1_engine', 'auto')
        )
        
        cached_result = self.cache.get_l2_segmentation(cache_key)
        if cached_result and not params.get('force_recompute', False):
            result.cache_hits['segmentation'] = True
            return cached_result
        
        # Import and run segmentation (deferred import to avoid circular deps)
        try:
            # This would normally import the actual segmentation module
            # For now, return a mock result
            segmentation_result = {
                'mask_png_b64': 'mock_mask_data',
                'item_rgba_png_b64': 'mock_item_data',
                'bbox': [10, 10, 100, 100],
                'mask_area_ratio': 0.15,
                'engine_used': params.get('phase1_engine', 'auto'),
                'fallback_used': False,
                'width': 768,
                'height': 768
            }
            
            # Cache result
            self.cache.set_l2_segmentation(cache_key, segmentation_result)
            result.cache_hits['segmentation'] = False
            
            return segmentation_result
            
        except Exception as e:
            logger.error(f"Segmentation failed: {e}")
            result.degraded = True
            result.processing_notes.append("segmentation_failed")
            
            # Return degradation mode - minimal mask
            return {
                'mask_png_b64': None,
                'item_rgba_png_b64': None,
                'mask_area_ratio': 0.0,
                'engine_used': 'degraded',
                'fallback_used': True,
                'degraded': True
            }
    
    async def _run_phase2_extraction(self, result: OrchestrationResult, **params) -> Dict[str, Any]:
        """Run Phase 2 color extraction with caching."""
        
        if result.segmentation_result.get('degraded'):
            # Degraded mode - return neutrals-only palette
            return {
                'palette': [
                    {'hex': '#FFFFFF', 'ratio': 0.4},
                    {'hex': '#F5F5F5', 'ratio': 0.3},
                    {'hex': '#D3D3D3', 'ratio': 0.3}
                ],
                'base_color': {
                    'hex': '#808080',
                    'cluster_index': 0,
                    'score_breakdown': {'fallback': True}
                },
                'degraded': True,
                'sampled_pixels': 0
            }
        
        # Check L2 cache
        filters = {k: v for k, v in params.items() if k.startswith('filter_') or k in ['k', 'max_samples']}
        cache_key = self.fingerprint_manager.get_extraction_cache_key(
            result.input_fingerprint['sha256'],
            params.get('gamma', config.DEFAULT_GAMMA),
            params.get('k', 5),
            filters
        )
        
        cached_result = self.cache.get_l2_extraction(cache_key)
        if cached_result and not params.get('force_recompute', False):
            result.cache_hits['extraction'] = True
            return cached_result
        
        # Run extraction (mock for now)
        try:
            extraction_result = {
                'palette': [
                    {'hex': '#000080', 'ratio': 0.6},
                    {'hex': '#FFFFFF', 'ratio': 0.25},
                    {'hex': '#C0C0C0', 'ratio': 0.15}
                ],
                'base_color': {
                    'hex': '#000080',
                    'cluster_index': 0,
                    'score_breakdown': {
                        'area_score': 0.6,
                        'saturation_score': 0.8,
                        'final_score': 0.7
                    }
                },
                'k': params.get('k', 5),
                'sampled_pixels': 15000,
                'width': result.segmentation_result.get('width', 768),
                'height': result.segmentation_result.get('height', 768)
            }
            
            # Cache result
            self.cache.set_l2_extraction(cache_key, extraction_result)
            result.cache_hits['extraction'] = False
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Color extraction failed: {e}")
            result.degraded = True
            result.processing_notes.append("extraction_failed")
            
            # Return neutral base
            return {
                'palette': [{'hex': '#808080', 'ratio': 1.0}],
                'base_color': {
                    'hex': '#808080',
                    'cluster_index': 0,
                    'score_breakdown': {'fallback': True}
                },
                'degraded': True
            }
    
    async def _run_phase3_harmony(self, result: OrchestrationResult, **params) -> Dict[str, Any]:
        """Run Phase 3 harmony generation with caching."""
        
        if not result.extraction_result or not result.extraction_result.get('base_color'):
            result.degraded = True
            result.processing_notes.append("no_base_color")
            
            # Return neutrals-only
            return {
                'suggestions': {
                    'neutral': [
                        {
                            'hex': '#FFFFFF',
                            'category': 'neutral',
                            'role_target': params.get('target_role', 'bottom'),
                            'rationale': ['category:neutral', 'fallback_mode']
                        }
                    ]
                },
                'degraded': True
            }
        
        # Check L2 cache
        harmony_params = {k: v for k, v in params.items() if k.startswith(('source_role', 'target_role', 'intent', 'season', 'include_'))}
        harmony_params['base_hex'] = result.extraction_result['base_color']['hex']
        
        cache_key = self.fingerprint_manager.get_advice_cache_key(
            result.input_fingerprint['sha256'],
            harmony_params
        )
        
        cached_result = self.cache.get_l2_advice(cache_key)
        if cached_result and not params.get('force_recompute', False):
            result.cache_hits['harmony'] = True
            return cached_result
        
        # Run harmony generation (mock for now)
        try:
            base_hex = result.extraction_result['base_color']['hex']
            
            suggestions_result = {
                'suggestions': {
                    'complementary': [
                        {
                            'hex': '#DBDB71',
                            'category': 'complementary',
                            'role_target': params.get('target_role', 'bottom'),
                            'hls': {'h': 0.167, 'l': 0.65, 's': 0.595},
                            'rationale': [
                                'category:complementary',
                                'h_rot:+180°; L→0.65 (dark base contrast)',
                                'S_ok:0.595',
                                'L_ok:0.650'
                            ]
                        }
                    ],
                    'neutral': [
                        {
                            'hex': '#FFFFFF',
                            'category': 'neutral',
                            'role_target': params.get('target_role', 'bottom'),
                            'rationale': ['category:neutral', 'base_lightness_ordering']
                        },
                        {
                            'hex': '#F5F5F5',
                            'category': 'neutral',
                            'role_target': params.get('target_role', 'bottom'),
                            'rationale': ['category:neutral', 'base_lightness_ordering']
                        }
                    ]
                },
                'policy': {
                    'delta_l_min': 0.12,
                    'version': self.policy_version
                }
            }
            
            # Cache result
            self.cache.set_l2_advice(cache_key, suggestions_result)
            result.cache_hits['harmony'] = False
            
            return suggestions_result
            
        except Exception as e:
            logger.error(f"Harmony generation failed: {e}")
            result.degraded = True
            result.processing_notes.append("harmony_failed")
            
            # Return base + neutrals
            return {
                'suggestions': {
                    'neutral': [
                        {
                            'hex': '#FFFFFF',
                            'category': 'neutral',
                            'role_target': params.get('target_role', 'bottom'),
                            'rationale': ['category:neutral', 'fallback_mode']
                        }
                    ]
                },
                'degraded': True
            }
    
    def _build_consolidated_response(self, result: OrchestrationResult, **params) -> Dict[str, Any]:
        """Build the final consolidated response."""
        
        response = {
            'request_id': result.request_id,
            'version': 'v1',
            'meta': {
                'input_mode': params.get('input_mode', 'unknown'),
                'source_role': params.get('source_role', 'top'),
                'target_role': params.get('target_role', 'bottom'),
                'intent': params.get('intent', 'classic'),
                'season': params.get('season', 'all')
            },
            'input_fingerprint': result.input_fingerprint,
            'segmentation': {
                'mask_area_ratio': result.segmentation_result.get('mask_area_ratio', 0.0),
                'engine_used': result.segmentation_result.get('engine_used', 'unknown'),
                'fallback_used': result.segmentation_result.get('fallback_used', False)
            },
            'extraction': {
                'palette': result.extraction_result.get('palette', []),
                'base_color': result.extraction_result.get('base_color', {}),
                'k': result.extraction_result.get('k', 5),
                'sampled_pixels': result.extraction_result.get('sampled_pixels', 0)
            },
            'suggestions': result.suggestions_result.get('suggestions', {}),
            'policy': result.suggestions_result.get('policy', {'version': self.policy_version}),
            'artifacts': {},  # TODO: Add swatch generation
            'from_cache': result.from_cache,
            'cache_keys': {},  # TODO: Add cache key reporting
            'debug': {
                'timings': result.timings,
                'cache_hits': result.cache_hits,
                'degraded': result.degraded,
                'processing_notes': result.processing_notes
            }
        }
        
        return response
    
    def _get_params_hash(self, **params) -> str:
        """Get hash of all parameters for cache keys."""
        # Filter out non-cacheable params
        cacheable_params = {k: v for k, v in params.items() 
                          if k not in ['force_recompute', 'cache_ok', 'idempotency_key']}
        
        return self.fingerprint_manager.generate_cache_key_digest(cacheable_params)[:12]
    
    async def _process_direct_harmony_mode(self, result: OrchestrationResult, base_hex: str, **params) -> Dict[str, Any]:
        """Process direct harmony mode (base_hex provided)."""
        
        # Mock implementation for direct harmony
        harmony_start = time.time()
        
        suggestions_result = {
            'suggestions': {
                'complementary': [
                    {
                        'hex': '#FF8000',  # Mock complementary
                        'category': 'complementary',
                        'role_target': params.get('target_role', 'bottom'),
                        'rationale': ['category:complementary', 'direct_mode']
                    }
                ]
            },
            'policy': {'version': self.policy_version}
        }
        
        result.timings['harmony_ms'] = round((time.time() - harmony_start) * 1000, 2)
        
        response = {
            'request_id': result.request_id,
            'version': 'v1',
            'meta': {
                'input_mode': 'artifacts_direct',
                'base_hex': base_hex
            },
            'suggestions': suggestions_result['suggestions'],
            'policy': suggestions_result['policy'],
            'from_cache': False,
            'debug': {
                'timings': result.timings,
                'processing_notes': ['direct_harmony_mode']
            }
        }
        
        return response
    
    async def _process_artifacts_mode(self, result: OrchestrationResult, mask_png_b64: str, item_rgba_png_b64: str, **params) -> Dict[str, Any]:
        """Process artifacts mode (mask + item provided)."""
        
        # Skip Phase 1, run Phase 2 and 3
        extraction_start = time.time()
        
        # Mock Phase 2 result
        result.extraction_result = {
            'palette': [{'hex': '#0000FF', 'ratio': 0.8}],
            'base_color': {
                'hex': '#0000FF',
                'cluster_index': 0,
                'score_breakdown': {'artifacts_mode': True}
            }
        }
        result.timings['extraction_ms'] = round((time.time() - extraction_start) * 1000, 2)
        
        # Run Phase 3
        harmony_start = time.time()
        result.suggestions_result = {
            'suggestions': {
                'complementary': [
                    {
                        'hex': '#FFFF00',
                        'category': 'complementary',
                        'role_target': params.get('target_role', 'bottom'),
                        'rationale': ['category:complementary', 'artifacts_mode']
                    }
                ]
            },
            'policy': {'version': self.policy_version}
        }
        result.timings['harmony_ms'] = round((time.time() - harmony_start) * 1000, 2)
        
        return self._build_consolidated_response(result, **params)
