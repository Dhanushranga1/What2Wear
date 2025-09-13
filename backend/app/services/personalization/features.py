"""
Feature computation engine for deriving user preferences from interaction events.
"""

import logging
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import json
import psycopg2
from psycopg2.extras import RealDictCursor

from . import UserFeatures

logger = logging.getLogger(__name__)


class FeatureComputer:
    """Computes user features from interaction events."""
    
    def __init__(self, db_connection_string: str):
        self.db_url = db_connection_string
        
        # Feature computation parameters
        self.decay_half_life_days = 14  # Events decay with 14-day half-life
        self.min_events_threshold = 5   # Minimum events to compute reliable features
        self.saturation_learning_rate = 0.1  # Learning rate for saturation preferences
        self.lightness_learning_rate = 0.1   # Learning rate for lightness preferences
        self.neutral_affinity_threshold = 0.6  # Threshold for neutral color preference
        
    def get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_url)
    
    def compute_features_for_user(self, user_id: str) -> UserFeatures:
        """Compute all features for a specific user."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get user events from last 90 days
                    cur.execute("""
                        SELECT event_type, timestamp_ms, data, created_at
                        FROM events 
                        WHERE user_id = %s 
                        AND timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '90 days') * 1000
                        ORDER BY timestamp_ms DESC
                    """, (user_id,))
                    
                    events = cur.fetchall()
                    
                    if len(events) < self.min_events_threshold:
                        # Not enough data for reliable features
                        return UserFeatures(
                            user_id=user_id,
                            hue_bias={},
                            neutral_affinity=0.0,
                            saturation_cap_adjust=0.0,
                            lightness_bias=0.0,
                            event_count=len(events),
                            updated_at=datetime.utcnow()
                        )
                    
                    # Compute individual features
                    hue_bias = self._compute_hue_bias(events)
                    neutral_affinity = self._compute_neutral_affinity(events)
                    saturation_cap_adjust = self._compute_saturation_preference(events)
                    lightness_bias = self._compute_lightness_bias(events)
                    
                    # Store computed features in database
                    self._store_computed_features(user_id, {
                        'hue_bias': hue_bias,
                        'neutral_affinity': neutral_affinity,
                        'saturation_cap_adjust': saturation_cap_adjust,
                        'lightness_bias': lightness_bias,
                        'event_count': len(events)
                    })
                    
                    return UserFeatures(
                        user_id=user_id,
                        hue_bias=hue_bias,
                        neutral_affinity=neutral_affinity,
                        saturation_cap_adjust=saturation_cap_adjust,
                        lightness_bias=lightness_bias,
                        event_count=len(events),
                        updated_at=datetime.utcnow()
                    )
        
        except Exception as e:
            logger.error(f"Error computing features for user {user_id}: {e}")
            # Return default features on error
            return UserFeatures(
                user_id=user_id,
                hue_bias={},
                neutral_affinity=0.0,
                saturation_cap_adjust=0.0,
                lightness_bias=0.0,
                event_count=0,
                updated_at=datetime.utcnow()
            )
    
    def _compute_time_weight(self, event_timestamp_ms: int) -> float:
        """Compute exponential decay weight based on event age."""
        
        current_time_ms = time.time() * 1000
        age_days = (current_time_ms - event_timestamp_ms) / (1000 * 60 * 60 * 24)
        
        # Exponential decay: weight = 0.5^(age_days / half_life_days)
        return math.pow(0.5, age_days / self.decay_half_life_days)
    
    def _compute_hue_bias(self, events: List[Dict]) -> Dict[str, float]:
        """Compute user's bias toward specific hues."""
        
        hue_weights = {}
        total_weight = 0.0
        
        for event in events:
            if event['event_type'] not in ['like', 'dislike', 'apply']:
                continue
            
            weight = self._compute_time_weight(event['timestamp_ms'])
            event_data = event['data']
            
            # Extract colors from event
            colors = event_data.get('colors', [])
            if not colors:
                continue
            
            # Determine sentiment: positive (like, apply) vs negative (dislike)
            sentiment = 1.0 if event['event_type'] in ['like', 'apply'] else -0.5
            
            # Extract hues from colors and update weights
            for color in colors:
                hue = self._extract_hue_from_color(color)
                if hue:
                    if hue not in hue_weights:
                        hue_weights[hue] = 0.0
                    hue_weights[hue] += weight * sentiment
                    total_weight += weight
        
        # Normalize weights
        if total_weight > 0:
            for hue in hue_weights:
                hue_weights[hue] /= total_weight
        
        # Filter out weak signals (less than 5% of average)
        avg_weight = sum(abs(w) for w in hue_weights.values()) / len(hue_weights) if hue_weights else 0
        threshold = avg_weight * 0.05
        
        return {hue: weight for hue, weight in hue_weights.items() if abs(weight) > threshold}
    
    def _compute_neutral_affinity(self, events: List[Dict]) -> float:
        """Compute user's preference for neutral colors."""
        
        neutral_score = 0.0
        total_weight = 0.0
        
        for event in events:
            if event['event_type'] not in ['like', 'dislike', 'apply']:
                continue
            
            weight = self._compute_time_weight(event['timestamp_ms'])
            event_data = event['data']
            colors = event_data.get('colors', [])
            
            if not colors:
                continue
            
            # Check if colors are neutral
            neutral_count = sum(1 for color in colors if self._is_neutral_color(color))
            neutral_ratio = neutral_count / len(colors)
            
            # Positive sentiment for likes/applies, negative for dislikes
            sentiment = 1.0 if event['event_type'] in ['like', 'apply'] else -0.5
            
            neutral_score += weight * sentiment * neutral_ratio
            total_weight += weight
        
        # Normalize and clamp to [-1, 1]
        if total_weight > 0:
            neutral_score /= total_weight
        
        return max(-1.0, min(1.0, neutral_score))
    
    def _compute_saturation_preference(self, events: List[Dict]) -> float:
        """Compute user's saturation preference adjustment."""
        
        saturation_score = 0.0
        total_weight = 0.0
        
        for event in events:
            if event['event_type'] not in ['like', 'dislike', 'apply']:
                continue
            
            weight = self._compute_time_weight(event['timestamp_ms'])
            event_data = event['data']
            colors = event_data.get('colors', [])
            
            if not colors:
                continue
            
            # Estimate average saturation of colors
            avg_saturation = self._estimate_average_saturation(colors)
            if avg_saturation is None:
                continue
            
            # Convert to preference adjustment (-1 to 1)
            # High saturation colors -> positive adjustment
            # Low saturation colors -> negative adjustment
            saturation_preference = (avg_saturation - 0.5) * 2  # Map [0,1] to [-1,1]
            
            sentiment = 1.0 if event['event_type'] in ['like', 'apply'] else -0.5
            
            saturation_score += weight * sentiment * saturation_preference
            total_weight += weight
        
        # Normalize and apply learning rate
        if total_weight > 0:
            saturation_score = (saturation_score / total_weight) * self.saturation_learning_rate
        
        return max(-1.0, min(1.0, saturation_score))
    
    def _compute_lightness_bias(self, events: List[Dict]) -> float:
        """Compute user's lightness preference."""
        
        lightness_score = 0.0
        total_weight = 0.0
        
        for event in events:
            if event['event_type'] not in ['like', 'dislike', 'apply']:
                continue
            
            weight = self._compute_time_weight(event['timestamp_ms'])
            event_data = event['data']
            colors = event_data.get('colors', [])
            
            if not colors:
                continue
            
            # Estimate average lightness of colors
            avg_lightness = self._estimate_average_lightness(colors)
            if avg_lightness is None:
                continue
            
            # Convert to bias (-1 for dark preference, +1 for light preference)
            lightness_preference = (avg_lightness - 0.5) * 2
            
            sentiment = 1.0 if event['event_type'] in ['like', 'apply'] else -0.5
            
            lightness_score += weight * sentiment * lightness_preference
            total_weight += weight
        
        # Normalize and apply learning rate
        if total_weight > 0:
            lightness_score = (lightness_score / total_weight) * self.lightness_learning_rate
        
        return max(-1.0, min(1.0, lightness_score))
    
    def _extract_hue_from_color(self, color: str) -> Optional[str]:
        """Extract hue category from color string."""
        
        color_lower = color.lower()
        
        # Simple hue mapping based on color names
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
        """Estimate average saturation of colors (simplified)."""
        
        # Simplified saturation estimation based on color names
        saturation_estimates = []
        
        for color in colors:
            color_lower = color.lower()
            
            # High saturation colors
            if any(keyword in color_lower for keyword in ['bright', 'vivid', 'neon', 'electric', 'vibrant']):
                saturation_estimates.append(0.9)
            # Medium saturation colors
            elif any(keyword in color_lower for keyword in ['deep', 'rich', 'bold']):
                saturation_estimates.append(0.7)
            # Low saturation colors
            elif any(keyword in color_lower for keyword in ['pale', 'light', 'soft', 'muted', 'pastel']):
                saturation_estimates.append(0.3)
            # Neutral colors (very low saturation)
            elif self._is_neutral_color(color):
                saturation_estimates.append(0.1)
            else:
                # Default medium saturation
                saturation_estimates.append(0.5)
        
        return sum(saturation_estimates) / len(saturation_estimates) if saturation_estimates else None
    
    def _estimate_average_lightness(self, colors: List[str]) -> Optional[float]:
        """Estimate average lightness of colors (simplified)."""
        
        lightness_estimates = []
        
        for color in colors:
            color_lower = color.lower()
            
            # Light colors
            if any(keyword in color_lower for keyword in ['light', 'pale', 'white', 'cream', 'ivory']):
                lightness_estimates.append(0.8)
            # Dark colors
            elif any(keyword in color_lower for keyword in ['dark', 'deep', 'black', 'navy', 'charcoal']):
                lightness_estimates.append(0.2)
            # Medium lightness
            else:
                lightness_estimates.append(0.5)
        
        return sum(lightness_estimates) / len(lightness_estimates) if lightness_estimates else None
    
    def _store_computed_features(self, user_id: str, features: Dict[str, Any]):
        """Store computed features in database."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO features (
                            user_id, hue_bias, neutral_affinity, saturation_cap_adjust,
                            lightness_bias, event_count, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (user_id) DO UPDATE SET
                            hue_bias = EXCLUDED.hue_bias,
                            neutral_affinity = EXCLUDED.neutral_affinity,
                            saturation_cap_adjust = EXCLUDED.saturation_cap_adjust,
                            lightness_bias = EXCLUDED.lightness_bias,
                            event_count = EXCLUDED.event_count,
                            updated_at = EXCLUDED.updated_at
                    """, (
                        user_id,
                        json.dumps(features['hue_bias']),
                        features['neutral_affinity'],
                        features['saturation_cap_adjust'],
                        features['lightness_bias'],
                        features['event_count']
                    ))
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error storing features for user {user_id}: {e}")
    
    def compute_features_batch(self, user_ids: List[str]) -> Dict[str, UserFeatures]:
        """Compute features for multiple users efficiently."""
        
        results = {}
        
        for user_id in user_ids:
            try:
                results[user_id] = self.compute_features_for_user(user_id)
            except Exception as e:
                logger.error(f"Error computing features for user {user_id}: {e}")
                results[user_id] = UserFeatures(
                    user_id=user_id,
                    hue_bias={},
                    neutral_affinity=0.0,
                    saturation_cap_adjust=0.0,
                    lightness_bias=0.0,
                    event_count=0,
                    updated_at=datetime.utcnow()
                )
        
        return results
    
    def get_stale_users(self, hours_threshold: int = 24) -> List[str]:
        """Get users whose features need recomputation."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT e.user_id
                        FROM events e
                        LEFT JOIN features f ON e.user_id = f.user_id
                        WHERE e.timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '7 days') * 1000
                        AND (f.updated_at IS NULL OR f.updated_at < NOW() - INTERVAL '%s hours')
                    """, (hours_threshold,))
                    
                    return [row[0] for row in cur.fetchall()]
        
        except Exception as e:
            logger.error(f"Error getting stale users: {e}")
            return []


# Factory function for dependency injection
def get_feature_computer() -> FeatureComputer:
    """Get feature computer instance."""
    import os
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not configured")
    
    return FeatureComputer(db_url)
