"""
Integration tests for Phase 5 personalization APIs.
"""

import json
import time
from datetime import datetime
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestProfileAPI:
    """Test cases for profile management API."""
    
    def test_get_user_preferences_new_user(self):
        """Test getting preferences for a new user."""
        
        # Mock authentication
        headers = {"Authorization": "Bearer user:test_user_123"}
        
        with patch('app.api.profile.get_db_connection') as mock_db:
            # Mock database responses for new user
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [
                None,  # No existing user record
                {  # Created user record
                    'user_id': 'test_user_123',
                    'created_at': datetime.utcnow(),
                    'last_seen_at': datetime.utcnow(),
                    'opt_out_personalization': False,
                    'opt_out_experiments': False
                },
                None  # No preferences record
            ]
            
            mock_conn = Mock()
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_db.return_value = mock_conn
            
            # Mock feature cache
            with patch('app.api.profile.get_feature_cache') as mock_cache:
                mock_cache_instance = Mock()
                mock_cache_instance.get_features_sync.return_value = Mock(
                    hue_bias={},
                    neutral_affinity=0.0,
                    saturation_cap_adjust=0.0,
                    lightness_bias=0.0,
                    event_count=0,
                    updated_at=datetime.utcnow()
                )
                mock_cache.return_value = mock_cache_instance
                
                response = client.get("/v1/profile/preferences", headers=headers)
                
                assert response.status_code == 200
                data = response.json()
                
                assert data['user_id'] == 'test_user_123'
                assert 'preferences' in data
                assert 'features' in data
                assert data['features']['event_count'] == 0
    
    def test_update_user_preferences(self):
        """Test updating user preferences."""
        
        headers = {"Authorization": "Bearer user:test_user_123"}
        
        preferences_data = {
            "avoid_hues": ["green", "purple"],
            "prefer_neutrals": True,
            "saturation_comfort": "medium",
            "lightness_comfort": "light",
            "season_bias": "spring_summer"
        }
        
        with patch('app.api.profile.get_db_connection') as mock_db:
            mock_cursor = Mock()
            mock_conn = Mock()
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_db.return_value = mock_conn
            
            # Mock cache invalidation
            with patch('app.api.profile.get_feature_cache') as mock_cache:
                mock_cache_instance = Mock()
                mock_cache.return_value = mock_cache_instance
                
                # Mock the subsequent GET request data
                with patch('app.api.profile.get_user_preferences') as mock_get:
                    mock_profile = Mock()
                    mock_profile.dict.return_value = {
                        'user_id': 'test_user_123',
                        'preferences': preferences_data,
                        'features': {'event_count': 0}
                    }
                    mock_get.return_value = mock_profile
                    
                    response = client.post(
                        "/v1/profile/preferences", 
                        json=preferences_data,
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    
                    # Verify cache was invalidated
                    mock_cache_instance.invalidate_cache_sync.assert_called_once_with('test_user_123')
    
    def test_invalid_preferences_validation(self):
        """Test validation of invalid preferences."""
        
        headers = {"Authorization": "Bearer user:test_user_123"}
        
        invalid_data = {
            "avoid_hues": ["invalid_color"],
            "saturation_comfort": "invalid_level"
        }
        
        response = client.post(
            "/v1/profile/preferences",
            json=invalid_data,
            headers=headers
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_data_deletion(self):
        """Test user data deletion."""
        
        headers = {"Authorization": "Bearer user:test_user_123"}
        
        deletion_request = {
            "user_id": "test_user_123",
            "confirmation": "DELETE_MY_DATA"
        }
        
        with patch('app.api.profile.get_db_connection') as mock_db:
            mock_cursor = Mock()
            mock_cursor.rowcount = 5  # Mock deleted rows
            
            mock_conn = Mock()
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_db.return_value = mock_conn
            
            with patch('app.api.profile.get_feature_cache') as mock_cache:
                mock_cache_instance = Mock()
                mock_cache.return_value = mock_cache_instance
                
                response = client.post(
                    "/v1/profile/delete",
                    json=deletion_request,
                    headers=headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data['status'] == 'success'
                assert 'deleted_records' in data


class TestEventsAPI:
    """Test cases for event ingestion API."""
    
    def test_single_event_ingestion(self):
        """Test ingesting a single event."""
        
        event_data = {
            "user_id": "test_user_123",
            "event": {
                "event_type": "like",
                "suggestion_id": "sugg_123",
                "colors": ["red", "white"],
                "context": {"source": "outfit_suggestions"}
            },
            "metadata": {
                "session_id": "session_123",
                "platform": "web"
            }
        }
        
        response = client.post("/v1/events/single", json=event_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'accepted'
        assert 'event_id' in data
        assert 'timestamp' in data
    
    def test_batch_event_ingestion(self):
        """Test ingesting a batch of events."""
        
        batch_data = {
            "user_id": "test_user_123",
            "events": [
                {
                    "event_type": "view",
                    "suggestion_id": "sugg_1", 
                    "colors": ["blue", "navy"]
                },
                {
                    "event_type": "like",
                    "suggestion_id": "sugg_2",
                    "colors": ["red", "white"]
                }
            ],
            "metadata": {
                "session_id": "session_123"
            }
        }
        
        response = client.post("/v1/events/batch", json=batch_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'accepted'
        assert data['event_count'] == 2
    
    def test_event_validation(self):
        """Test event data validation."""
        
        invalid_event = {
            "user_id": "test_user_123",
            "event": {
                "event_type": "invalid_type",  # Invalid event type
                "colors": ["red"]
            }
        }
        
        response = client.post("/v1/events/single", json=invalid_event)
        
        assert response.status_code == 422  # Validation error
    
    def test_events_health_check(self):
        """Test events pipeline health endpoint."""
        
        with patch('app.api.events.get_db_connection') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [
                (10,),  # 10 events in last hour
                (2,)    # 2 events in last 5 minutes
            ]
            
            mock_conn = Mock()
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_db.return_value = mock_conn
            
            response = client.get("/v1/events/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'healthy'
            assert data['events_last_hour'] == 10
            assert data['events_last_5min'] == 2


class TestAnalyticsAPI:
    """Test cases for analytics and KPIs API."""
    
    def test_overall_kpis(self):
        """Test getting overall KPIs."""
        
        with patch('app.api.phase5_analytics.get_db_connection') as mock_db:
            # Mock database responses for KPI queries
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [
                {'total_sessions': 100, 'personalized_sessions': 75, 'avg_reranking_time_ms': 15.5},  # Personalization KPIs
                {'users_with_recent_features': 50},  # Feature health
                {'total_active_users': 80},  # Active users
                {'total_events': 500, 'unique_users': 80},  # Engagement metrics
                (25,),  # Recent events count
            ]
            
            # Mock fetchall for event breakdown and experiments
            mock_cursor.fetchall.side_effect = [
                [{'event_type': 'like', 'count': 200}, {'event_type': 'view', 'count': 300}],  # Event breakdown
                [],  # Experiments (empty)
                []   # Experiment variant stats (empty)
            ]
            
            mock_conn = Mock()
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_db.return_value = mock_conn
            
            response = client.get("/v1/analytics/kpis?days=7")
            
            assert response.status_code == 200
            data = response.json()
            
            assert 'personalization' in data
            assert 'engagement' in data
            assert 'experiments' in data
            assert 'feature_health' in data
            
            # Check personalization metrics
            personalization = data['personalization']
            assert personalization['total_sessions'] == 100
            assert personalization['personalized_sessions'] == 75
            assert personalization['personalization_rate'] == 75.0
    
    def test_phase5_health_check(self):
        """Test Phase 5 system health check."""
        
        with patch('app.api.phase5_analytics.get_db_connection') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = {
                'events_last_hour': 5,
                'sessions_last_hour': 3,
                'features_updated_24h': 10,
                'active_experiments': 2
            }
            
            mock_conn = Mock()
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_db.return_value = mock_conn
            
            response = client.get("/v1/analytics/health/phase5")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data['status'] == 'healthy'
            assert 'component_health' in data
            assert 'statistics' in data


class TestPersonalizationIntegration:
    """Integration tests for the complete personalization flow."""
    
    def test_suggestion_with_personalization(self):
        """Test getting suggestions with personalization applied."""
        
        headers = {"Authorization": "Bearer user:test_user_123"}
        
        # Mock the entire suggestion flow
        with patch('main.conn') as mock_conn:
            # Mock database queries
            mock_cursor = Mock()
            
            # Source garment query
            mock_cursor.fetchone.side_effect = [
                ('garment_123', 'top', 'path/to/image.jpg', ['red', 'white'], ['casual']),  # Source garment
                (False, False),  # User opt-out preferences
            ]
            
            # Candidate garments query  
            mock_cursor.fetchall.return_value = [
                ('garment_456', 'path/to/candidate1.jpg', ['blue', 'navy'], ['formal']),
                ('garment_789', 'path/to/candidate2.jpg', ['gray', 'black'], ['business'])
            ]
            
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
            
            # Mock personalization components
            with patch('app.services.personalization.get_feature_cache') as mock_cache:
                mock_cache_instance = Mock()
                mock_cache_instance.get_features_sync.return_value = Mock(
                    user_id='test_user_123',
                    hue_bias={'blue': 0.3, 'red': -0.1},
                    neutral_affinity=0.2,
                    saturation_cap_adjust=0.1,
                    lightness_bias=0.0,
                    event_count=20,
                    updated_at=datetime.utcnow()
                )
                mock_cache.return_value = mock_cache_instance
                
                with patch('app.services.personalization.ranking.get_personalized_ranker') as mock_ranker:
                    mock_ranker_instance = Mock()
                    mock_result = Mock()
                    mock_result.suggestions = [
                        Mock(
                            suggestion_id='sugg_garment_123_456',
                            colors=['blue', 'navy'],
                            base_score=0.85,
                            metadata={'reasons': ['color_harmony'], 'image_path': 'path/to/candidate1.jpg'}
                        )
                    ]
                    mock_result.personalization_applied = True
                    mock_result.experiment_variant = 'treatment_a'
                    mock_result.reranking_time_ms = 12.5
                    
                    mock_ranker_instance.rerank_with_personalization.return_value = mock_result
                    mock_ranker.return_value = mock_ranker_instance
                    
                    # Mock URL signing
                    with patch('main.create_signed_url') as mock_sign:
                        mock_sign.return_value = 'https://signed-url.com/image.jpg'
                        
                        response = client.get("/suggest/garment_123", headers=headers)
                        
                        assert response.status_code == 200
                        data = response.json()
                        
                        assert data['source_id'] == 'garment_123'
                        assert len(data['suggestions']) >= 0
                        
                        # Verify personalization was called
                        mock_ranker_instance.rerank_with_personalization.assert_called_once()


def test_authentication_required():
    """Test that authentication is required for protected endpoints."""
    
    # Test without authentication header
    response = client.get("/v1/profile/preferences")
    assert response.status_code == 403  # or 401 depending on implementation
    
    # Test with invalid token
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/v1/profile/preferences", headers=headers)
    assert response.status_code == 401
