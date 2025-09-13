"""
Phase 5 Personalized Re-ranking Layer.
Applies user features to re-rank Phase 3 color suggestions.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import math

from . import UserFeatures
from .experiments import get_experiment_manager

logger = logging.getLogger(__name__)


@dataclass
class SuggestionItem:
    """A color suggestion item with metadata."""
    suggestion_id: str
    colors: List[str]
    base_score: float
    metadata: Dict[str, Any]
    original_rank: int


@dataclass
class RerankingResult:
    """Result of personalized re-ranking."""
    suggestions: List[SuggestionItem]
    personalization_applied: bool
    experiment_variant: Optional[str]
    reranking_time_ms: float
    score_adjustments: Dict[str, float]


class PersonalizedRanker:
    """Applies personalized re-ranking to color suggestions."""
    
    def __init__(self):
        # Re-ranking parameters
        self.hue_bias_weight = 0.3        # Weight for hue preference bias
        self.neutral_affinity_weight = 0.2 # Weight for neutral color preference
        self.saturation_weight = 0.15      # Weight for saturation preference
        self.lightness_weight = 0.15       # Weight for lightness preference
        self.diversity_weight = 0.2        # Weight for maintaining diversity
        
        # Thresholds
        self.min_score_threshold = 0.1     # Minimum base score to consider
        self.max_boost_factor = 1.5        # Maximum boost multiplier
        self.max_penalty_factor = 0.7      # Maximum penalty multiplier
        
    def rerank_suggestions(
        self, 
        suggestions: List[Dict[str, Any]], 
        user_features: UserFeatures,
        experiment_assignments: Dict[str, str] = None,
        context: Dict[str, Any] = None
    ) -> RerankingResult:
        """Apply personalized re-ranking to suggestions."""
        
        start_time = time.time()
        experiment_variant = None
        personalization_applied = False
        
        # Convert to SuggestionItem objects
        suggestion_items = []
        for i, suggestion in enumerate(suggestions):
            item = SuggestionItem(
                suggestion_id=suggestion.get('suggestion_id', f'suggestion_{i}'),
                colors=suggestion.get('colors', []),
                base_score=suggestion.get('score', 1.0),
                metadata=suggestion.get('metadata', {}),
                original_rank=i
            )
            suggestion_items.append(item)
        
        # Check if personalization should be applied
        if not self._should_apply_personalization(user_features, experiment_assignments):
            return RerankingResult(
                suggestions=suggestion_items,
                personalization_applied=False,
                experiment_variant=experiment_variant,
                reranking_time_ms=(time.time() - start_time) * 1000,
                score_adjustments={}
            )
        
        # Get experiment variant for personalization algorithm
        experiment_assignments = experiment_assignments or {}
        experiment_variant = experiment_assignments.get('personalization_algorithm', 'control')
        
        # Apply personalized scoring
        score_adjustments = {}
        for item in suggestion_items:
            adjustment = self._compute_personalization_score(
                item, user_features, experiment_variant, context
            )
            item.base_score *= adjustment
            score_adjustments[item.suggestion_id] = adjustment
        
        # Re-rank based on updated scores
        suggestion_items.sort(key=lambda x: x.base_score, reverse=True)
        
        # Apply diversity filtering if enabled
        if experiment_variant in ['treatment_a', 'treatment_b']:
            suggestion_items = self._apply_diversity_filtering(suggestion_items, user_features)
        
        personalization_applied = True
        reranking_time_ms = (time.time() - start_time) * 1000
        
        logger.debug(f"Re-ranked {len(suggestion_items)} suggestions in {reranking_time_ms:.2f}ms")
        
        return RerankingResult(
            suggestions=suggestion_items,
            personalization_applied=personalization_applied,
            experiment_variant=experiment_variant,
            reranking_time_ms=reranking_time_ms,
            score_adjustments=score_adjustments
        )
    
    def _should_apply_personalization(
        self, 
        user_features: UserFeatures, 
        experiment_assignments: Dict[str, str] = None
    ) -> bool:
        """Determine if personalization should be applied."""
        
        # Check if user has enough data for reliable personalization
        if user_features.event_count < 5:
            return False
        
        # Check experiment assignment
        experiment_assignments = experiment_assignments or {}
        variant = experiment_assignments.get('personalization_algorithm', 'control')
        
        return variant != 'control'
    
    def _compute_personalization_score(
        self,
        item: SuggestionItem,
        user_features: UserFeatures,
        experiment_variant: str,
        context: Dict[str, Any] = None
    ) -> float:
        """Compute personalization score adjustment for a suggestion."""
        
        if item.base_score < self.min_score_threshold:
            return 1.0  # Don't adjust very low-scoring items
        
        total_adjustment = 1.0
        context = context or {}
        
        # Apply hue bias adjustments
        hue_adjustment = self._compute_hue_bias_adjustment(item.colors, user_features.hue_bias)
        total_adjustment *= (1.0 + hue_adjustment * self.hue_bias_weight)
        
        # Apply neutral affinity adjustments
        neutral_adjustment = self._compute_neutral_affinity_adjustment(item.colors, user_features.neutral_affinity)
        total_adjustment *= (1.0 + neutral_adjustment * self.neutral_affinity_weight)
        
        # Apply saturation preference adjustments
        saturation_adjustment = self._compute_saturation_adjustment(item.colors, user_features.saturation_cap_adjust)
        total_adjustment *= (1.0 + saturation_adjustment * self.saturation_weight)
        
        # Apply lightness preference adjustments
        lightness_adjustment = self._compute_lightness_adjustment(item.colors, user_features.lightness_bias)
        total_adjustment *= (1.0 + lightness_adjustment * self.lightness_weight)
        
        # Apply experiment-specific adjustments
        if experiment_variant == 'treatment_a':
            # More aggressive personalization
            total_adjustment = 1.0 + (total_adjustment - 1.0) * 1.5
        elif experiment_variant == 'treatment_b':
            # Conservative personalization with diversity boost
            total_adjustment = 1.0 + (total_adjustment - 1.0) * 0.8
        
        # Clamp to reasonable bounds
        return max(self.max_penalty_factor, min(self.max_boost_factor, total_adjustment))
    
    def _compute_hue_bias_adjustment(self, colors: List[str], hue_bias: Dict[str, float]) -> float:
        """Compute adjustment based on user's hue preferences."""
        
        if not hue_bias or not colors:
            return 0.0
        
        total_bias = 0.0
        color_count = 0
        
        for color in colors:
            hue = self._extract_hue_from_color(color)
            if hue and hue in hue_bias:
                total_bias += hue_bias[hue]
                color_count += 1
        
        if color_count == 0:
            return 0.0
        
        avg_bias = total_bias / color_count
        
        # Convert bias to adjustment factor (-1 to 1 becomes -0.5 to 0.5)
        return avg_bias * 0.5
    
    def _compute_neutral_affinity_adjustment(self, colors: List[str], neutral_affinity: float) -> float:
        """Compute adjustment based on user's neutral color preference."""
        
        if not colors:
            return 0.0
        
        neutral_count = sum(1 for color in colors if self._is_neutral_color(color))
        neutral_ratio = neutral_count / len(colors)
        
        # If user likes neutrals and this has neutrals, boost it
        # If user dislikes neutrals and this has neutrals, penalize it
        adjustment = neutral_affinity * neutral_ratio
        
        # Scale adjustment
        return adjustment * 0.3
    
    def _compute_saturation_adjustment(self, colors: List[str], saturation_preference: float) -> float:
        """Compute adjustment based on user's saturation preference."""
        
        if not colors:
            return 0.0
        
        avg_saturation = self._estimate_average_saturation(colors)
        if avg_saturation is None:
            return 0.0
        
        # If user prefers high saturation and this is high saturation, boost
        # If user prefers low saturation and this is low saturation, boost
        saturation_score = (avg_saturation - 0.5) * 2  # Map [0,1] to [-1,1]
        alignment = saturation_preference * saturation_score
        
        return alignment * 0.2
    
    def _compute_lightness_adjustment(self, colors: List[str], lightness_bias: float) -> float:
        """Compute adjustment based on user's lightness preference."""
        
        if not colors:
            return 0.0
        
        avg_lightness = self._estimate_average_lightness(colors)
        if avg_lightness is None:
            return 0.0
        
        # Convert lightness to bias score
        lightness_score = (avg_lightness - 0.5) * 2  # Map [0,1] to [-1,1]
        alignment = lightness_bias * lightness_score
        
        return alignment * 0.2
    
    def _apply_diversity_filtering(self, items: List[SuggestionItem], user_features: UserFeatures) -> List[SuggestionItem]:
        """Apply diversity filtering to maintain variety in top results."""
        
        if len(items) <= 3:
            return items
        
        # Keep top item as is
        filtered_items = [items[0]]
        
        for item in items[1:]:
            # Check diversity against already selected items
            if self._maintains_diversity(item, filtered_items, user_features):
                filtered_items.append(item)
            
            # Stop when we have enough diverse items
            if len(filtered_items) >= len(items):
                break
        
        # Fill remaining slots with original order if needed
        remaining_items = [item for item in items if item not in filtered_items]
        filtered_items.extend(remaining_items[:len(items) - len(filtered_items)])
        
        return filtered_items
    
    def _maintains_diversity(self, item: SuggestionItem, selected_items: List[SuggestionItem], user_features: UserFeatures) -> bool:
        """Check if adding this item maintains diversity."""
        
        if not selected_items:
            return True
        
        # Check hue diversity
        item_hues = set(self._extract_hue_from_color(color) for color in item.colors if self._extract_hue_from_color(color))
        
        for selected in selected_items:
            selected_hues = set(self._extract_hue_from_color(color) for color in selected.colors if self._extract_hue_from_color(color))
            
            # If there's significant overlap, consider it less diverse
            if item_hues and selected_hues:
                overlap = len(item_hues.intersection(selected_hues)) / len(item_hues.union(selected_hues))
                if overlap > 0.7:  # More than 70% overlap
                    return False
        
        return True
    
    def _extract_hue_from_color(self, color: str) -> Optional[str]:
        """Extract hue category from color string."""
        
        color_lower = color.lower()
        
        hue_mappings = {
            'red': ['red', 'crimson', 'scarlet', 'burgundy', 'maroon'],
            'orange': ['orange', 'coral', 'peach', 'tangerine'],
            'yellow': ['yellow', 'gold', 'amber', 'lemon'],
            'green': ['green', 'lime', 'forest', 'olive', 'teal'],
            'blue': ['blue', 'navy', 'royal', 'sky', 'azure'],
            'purple': ['purple', 'violet', 'indigo', 'lavender', 'plum'],
            'pink': ['pink', 'rose', 'magenta', 'fuchsia'],
            'brown': ['brown', 'tan', 'beige', 'khaki', 'coffee'],
            'gray': ['gray', 'grey', 'silver', 'charcoal']
        }
        
        for hue, color_names in hue_mappings.items():
            if any(name in color_lower for name in color_names):
                return hue
        
        return None
    
    def _is_neutral_color(self, color: str) -> bool:
        """Check if a color is neutral."""
        
        color_lower = color.lower()
        neutral_keywords = ['white', 'black', 'gray', 'grey', 'beige', 'cream', 'ivory', 'charcoal', 'silver']
        
        return any(keyword in color_lower for keyword in neutral_keywords)
    
    def _estimate_average_saturation(self, colors: List[str]) -> Optional[float]:
        """Estimate average saturation of colors."""
        
        saturation_estimates = []
        
        for color in colors:
            color_lower = color.lower()
            
            if any(keyword in color_lower for keyword in ['bright', 'vivid', 'neon', 'electric', 'vibrant']):
                saturation_estimates.append(0.9)
            elif any(keyword in color_lower for keyword in ['deep', 'rich', 'bold']):
                saturation_estimates.append(0.7)
            elif any(keyword in color_lower for keyword in ['pale', 'light', 'soft', 'muted', 'pastel']):
                saturation_estimates.append(0.3)
            elif self._is_neutral_color(color):
                saturation_estimates.append(0.1)
            else:
                saturation_estimates.append(0.5)
        
        return sum(saturation_estimates) / len(saturation_estimates) if saturation_estimates else None
    
    def _estimate_average_lightness(self, colors: List[str]) -> Optional[float]:
        """Estimate average lightness of colors."""
        
        lightness_estimates = []
        
        for color in colors:
            color_lower = color.lower()
            
            if any(keyword in color_lower for keyword in ['light', 'pale', 'white', 'cream', 'ivory']):
                lightness_estimates.append(0.8)
            elif any(keyword in color_lower for keyword in ['dark', 'deep', 'black', 'navy', 'charcoal']):
                lightness_estimates.append(0.2)
            else:
                lightness_estimates.append(0.5)
        
        return sum(lightness_estimates) / len(lightness_estimates) if lightness_estimates else None


class RerankingOrchestrator:
    """Orchestrates the personalized re-ranking process."""
    
    def __init__(self):
        self.ranker = PersonalizedRanker()
        self.experiment_manager = None
        
    def get_experiment_manager(self):
        """Lazy load experiment manager."""
        if self.experiment_manager is None:
            self.experiment_manager = get_experiment_manager()
        return self.experiment_manager
    
    def rerank_with_personalization(
        self,
        suggestions: List[Dict[str, Any]],
        user_id: str,
        user_features: UserFeatures,
        context: Dict[str, Any] = None
    ) -> RerankingResult:
        """Full personalized re-ranking with experiment assignment."""
        
        start_time = time.time()
        
        try:
            # Get experiment assignments
            exp_manager = self.get_experiment_manager()
            experiment_assignments = exp_manager.assign_user_to_experiments(user_id, context)
            
            # Apply re-ranking
            result = self.ranker.rerank_suggestions(
                suggestions, user_features, experiment_assignments, context
            )
            
            # Track exposure for personalization experiments
            if result.experiment_variant and result.experiment_variant != 'control':
                exp_manager.track_exposure(user_id, 'personalization_algorithm', result.experiment_variant)
            
            return result
        
        except Exception as e:
            logger.error(f"Error in personalized re-ranking for user {user_id}: {e}")
            
            # Fallback to original suggestions
            suggestion_items = []
            for i, suggestion in enumerate(suggestions):
                item = SuggestionItem(
                    suggestion_id=suggestion.get('suggestion_id', f'suggestion_{i}'),
                    colors=suggestion.get('colors', []),
                    base_score=suggestion.get('score', 1.0),
                    metadata=suggestion.get('metadata', {}),
                    original_rank=i
                )
                suggestion_items.append(item)
            
            return RerankingResult(
                suggestions=suggestion_items,
                personalization_applied=False,
                experiment_variant=None,
                reranking_time_ms=(time.time() - start_time) * 1000,
                score_adjustments={}
            )


# Factory function for dependency injection
def get_personalized_ranker() -> RerankingOrchestrator:
    """Get personalized ranker instance."""
    return RerankingOrchestrator()
