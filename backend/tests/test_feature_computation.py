"""
Unit tests for Phase 5 feature computation engine.
"""

import pytest
from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch, MagicMock

from app.services.personalization.features import FeatureComputer
from app.services.personalization import UserFeatures


class TestFeatureComputer:
    """Test cases for FeatureComputer."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_db_url = "postgresql://test:test@localhost/test"
        self.feature_computer = FeatureComputer(self.mock_db_url)
    
    def test_time_weight_computation(self):
        """Test exponential decay weight computation."""
        import time
        
        current_time = time.time() * 1000
        
        # Recent event (1 day ago)
        recent_timestamp = current_time - (24 * 60 * 60 * 1000)
        recent_weight = self.feature_computer._compute_time_weight(recent_timestamp)
        
        # Old event (14 days ago - half life)
        old_timestamp = current_time - (14 * 24 * 60 * 60 * 1000)
        old_weight = self.feature_computer._compute_time_weight(old_timestamp)
        
        # Very old event (28 days ago - two half lives)
        very_old_timestamp = current_time - (28 * 24 * 60 * 60 * 1000)
        very_old_weight = self.feature_computer._compute_time_weight(very_old_timestamp)
        
        # Assertions
        assert 0.8 < recent_weight <= 1.0, "Recent events should have high weight"
        assert 0.4 < old_weight < 0.6, "14-day old events should have ~0.5 weight"
        assert 0.2 < very_old_weight < 0.3, "28-day old events should have ~0.25 weight"
        assert recent_weight > old_weight > very_old_weight, "Weights should decay over time"
    
    def test_hue_extraction(self):
        """Test hue extraction from color names."""
        test_cases = [
            ("red", "red"),
            ("crimson", "red"),
            ("navy blue", "blue"),
            ("forest green", "green"),
            ("purple", "purple"),
            ("silver", "gray"),
            ("unknown_color", None)
        ]
        
        for color, expected_hue in test_cases:
            result = self.feature_computer._extract_hue_from_color(color)
            assert result == expected_hue, f"Color '{color}' should map to hue '{expected_hue}'"
    
    def test_neutral_color_detection(self):
        """Test neutral color detection."""
        neutral_colors = ["white", "black", "gray", "grey", "beige", "cream", "ivory", "charcoal"]
        non_neutral_colors = ["red", "blue", "green", "purple", "yellow"]
        
        for color in neutral_colors:
            assert self.feature_computer._is_neutral_color(color), f"'{color}' should be detected as neutral"
        
        for color in non_neutral_colors:
            assert not self.feature_computer._is_neutral_color(color), f"'{color}' should not be detected as neutral"
    
    def test_saturation_estimation(self):
        """Test saturation estimation."""
        high_sat_colors = ["bright red", "vivid blue", "neon green"]
        low_sat_colors = ["pale pink", "light blue", "muted yellow"]
        neutral_colors = ["gray", "beige", "white"]
        
        high_sat = self.feature_computer._estimate_average_saturation(high_sat_colors)
        low_sat = self.feature_computer._estimate_average_saturation(low_sat_colors)
        neutral_sat = self.feature_computer._estimate_average_saturation(neutral_colors)
        
        assert high_sat > 0.7, "High saturation colors should have high saturation estimate"
        assert low_sat < 0.5, "Low saturation colors should have low saturation estimate"
        assert neutral_sat < 0.2, "Neutral colors should have very low saturation estimate"
        assert high_sat > low_sat > neutral_sat, "Saturation estimates should be ordered correctly"
    
    def test_lightness_estimation(self):
        """Test lightness estimation."""
        light_colors = ["light blue", "pale yellow", "white", "cream"]
        dark_colors = ["dark red", "deep blue", "black", "charcoal"]
        medium_colors = ["red", "blue", "green"]
        
        light_est = self.feature_computer._estimate_average_lightness(light_colors)
        dark_est = self.feature_computer._estimate_average_lightness(dark_colors)
        medium_est = self.feature_computer._estimate_average_lightness(medium_colors)
        
        assert light_est > 0.6, "Light colors should have high lightness estimate"
        assert dark_est < 0.4, "Dark colors should have low lightness estimate"
        assert 0.4 <= medium_est <= 0.6, "Medium colors should have medium lightness estimate"
    
    @patch('app.services.personalization.features.FeatureComputer.get_db_connection')
    def test_hue_bias_computation(self, mock_get_db):
        """Test hue bias computation from events."""
        import time
        
        current_time = int(time.time() * 1000)
        
        # Mock events data
        mock_events = [
            {
                'event_type': 'like',
                'timestamp_ms': current_time - 1000,
                'data': {'colors': ['red', 'crimson']},
                'created_at': datetime.utcnow()
            },
            {
                'event_type': 'like', 
                'timestamp_ms': current_time - 2000,
                'data': {'colors': ['blue', 'navy']},
                'created_at': datetime.utcnow()
            },
            {
                'event_type': 'dislike',
                'timestamp_ms': current_time - 3000,
                'data': {'colors': ['green']},
                'created_at': datetime.utcnow()
            }
        ]
        
        hue_bias = self.feature_computer._compute_hue_bias(mock_events)
        
        # Red and blue should have positive bias, green should have negative bias
        assert hue_bias.get('red', 0) > 0, "Red should have positive bias from likes"
        assert hue_bias.get('blue', 0) > 0, "Blue should have positive bias from likes" 
        assert hue_bias.get('green', 0) < 0, "Green should have negative bias from dislike"
    
    @patch('app.services.personalization.features.FeatureComputer.get_db_connection')
    def test_neutral_affinity_computation(self, mock_get_db):
        """Test neutral affinity computation."""
        import time
        
        current_time = int(time.time() * 1000)
        
        # Events with neutral colors liked
        neutral_events = [
            {
                'event_type': 'like',
                'timestamp_ms': current_time - 1000,
                'data': {'colors': ['gray', 'beige']},
                'created_at': datetime.utcnow()
            },
            {
                'event_type': 'like',
                'timestamp_ms': current_time - 2000,
                'data': {'colors': ['white', 'cream']},
                'created_at': datetime.utcnow()
            }
        ]
        
        neutral_affinity = self.feature_computer._compute_neutral_affinity(neutral_events)
        assert neutral_affinity > 0, "Should have positive neutral affinity when neutral colors are liked"
        
        # Events with colorful colors liked
        colorful_events = [
            {
                'event_type': 'like',
                'timestamp_ms': current_time - 1000,
                'data': {'colors': ['red', 'blue']},
                'created_at': datetime.utcnow()
            },
            {
                'event_type': 'dislike',
                'timestamp_ms': current_time - 2000,
                'data': {'colors': ['gray', 'beige']},
                'created_at': datetime.utcnow()
            }
        ]
        
        colorful_affinity = self.feature_computer._compute_neutral_affinity(colorful_events)
        assert colorful_affinity < 0, "Should have negative neutral affinity when neutrals are disliked"
    
    @patch('app.services.personalization.features.FeatureComputer.get_db_connection')
    def test_insufficient_events_handling(self, mock_get_db):
        """Test handling of users with insufficient events."""
        
        # Mock database cursor
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []  # No events
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        
        mock_get_db.return_value = mock_conn
        
        result = self.feature_computer.compute_features_for_user("test_user")
        
        # Should return default features
        assert isinstance(result, UserFeatures)
        assert result.user_id == "test_user"
        assert result.event_count == 0
        assert result.hue_bias == {}
        assert result.neutral_affinity == 0.0
        assert result.saturation_cap_adjust == 0.0
        assert result.lightness_bias == 0.0
    
    @patch('app.services.personalization.features.FeatureComputer.get_db_connection')
    def test_error_handling(self, mock_get_db):
        """Test error handling in feature computation."""
        
        # Mock database connection failure
        mock_get_db.side_effect = Exception("Database connection failed")
        
        result = self.feature_computer.compute_features_for_user("test_user")
        
        # Should return default features on error
        assert isinstance(result, UserFeatures)
        assert result.event_count == 0
    
    def test_feature_storage(self):
        """Test feature storage in database."""
        
        with patch.object(self.feature_computer, 'get_db_connection') as mock_get_db:
            mock_cursor = Mock()
            mock_conn = Mock()
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_get_db.return_value = mock_conn
            
            test_features = {
                'hue_bias': {'red': 0.3, 'blue': -0.1},
                'neutral_affinity': 0.2,
                'saturation_cap_adjust': 0.1,
                'lightness_bias': -0.05,
                'event_count': 15
            }
            
            self.feature_computer._store_computed_features("test_user", test_features)
            
            # Verify database call was made
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            
            assert "INSERT INTO features" in call_args[0]
            assert call_args[1][0] == "test_user"  # user_id
            assert json.loads(call_args[1][1]) == test_features['hue_bias']  # hue_bias JSON


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    import time
    current_time = int(time.time() * 1000)
    
    return [
        {
            'event_type': 'like',
            'timestamp_ms': current_time - 1000,
            'data': {'colors': ['red', 'white']},
            'created_at': datetime.utcnow()
        },
        {
            'event_type': 'like',
            'timestamp_ms': current_time - 2000,
            'data': {'colors': ['blue', 'navy']},
            'created_at': datetime.utcnow()
        },
        {
            'event_type': 'apply',
            'timestamp_ms': current_time - 3000,
            'data': {'colors': ['gray', 'charcoal']},
            'created_at': datetime.utcnow()
        },
        {
            'event_type': 'dislike',
            'timestamp_ms': current_time - 4000,
            'data': {'colors': ['green', 'lime']},
            'created_at': datetime.utcnow()
        }
    ]


def test_integration_feature_computation(sample_events):
    """Integration test for complete feature computation."""
    
    # This would require a real database connection in a full integration test
    # For now, we'll test the computational logic with mocked data
    
    feature_computer = FeatureComputer("mock://db")
    
    # Test each computation method with sample events
    hue_bias = feature_computer._compute_hue_bias(sample_events)
    neutral_affinity = feature_computer._compute_neutral_affinity(sample_events)
    saturation_preference = feature_computer._compute_saturation_preference(sample_events)
    lightness_bias = feature_computer._compute_lightness_bias(sample_events)
    
    # Verify reasonable results
    assert isinstance(hue_bias, dict)
    assert isinstance(neutral_affinity, float)
    assert isinstance(saturation_preference, float)
    assert isinstance(lightness_bias, float)
    
    assert -1.0 <= neutral_affinity <= 1.0
    assert -1.0 <= saturation_preference <= 1.0
    assert -1.0 <= lightness_bias <= 1.0
