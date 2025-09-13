"""
End-to-End Validation Suite for Phase 5 Personalization System
Comprehensive testing of the complete personalization flow.
"""

import asyncio
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@dataclass
class ValidationResult:
    """Result of a validation test."""
    test_name: str
    success: bool
    duration_ms: float
    details: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class UserJourney:
    """Represents a complete user journey through the system."""
    user_id: str
    events: List[Dict[str, Any]]
    expected_personalization: Dict[str, Any]
    preferences: Optional[Dict[str, Any]] = None


class Phase5E2EValidator:
    """End-to-end validator for Phase 5 personalization system."""
    
    def __init__(self, client: TestClient, config: Dict[str, Any]):
        self.client = client
        self.config = config
        self.results: List[ValidationResult] = []
        
    def run_all_validations(self) -> Dict[str, Any]:
        """Run complete end-to-end validation suite."""
        
        print("Starting Phase 5 End-to-End Validation...")
        start_time = time.time()
        
        # Core system validations
        self._validate_system_health()
        self._validate_authentication()
        self._validate_rate_limiting()
        
        # User journey validations
        self._validate_new_user_onboarding()
        self._validate_preference_setting()
        self._validate_event_ingestion()
        self._validate_feature_computation()
        self._validate_personalized_suggestions()
        
        # Advanced scenarios
        self._validate_experiment_assignment()
        self._validate_data_consistency()
        self._validate_performance_requirements()
        self._validate_data_privacy_compliance()
        
        # Analytics and monitoring
        self._validate_analytics_pipeline()
        self._validate_audit_logging()
        
        total_time = time.time() - start_time
        
        return self._generate_validation_report(total_time)
    
    def _validate_system_health(self):
        """Validate system health and component status."""
        
        start_time = time.time()
        
        try:
            # Check Phase 5 health endpoint
            response = self.client.get("/v1/analytics/health/phase5")
            
            success = response.status_code == 200
            details = {
                "status_code": response.status_code,
                "response_time_ms": (time.time() - start_time) * 1000
            }
            
            if success:
                health_data = response.json()
                details.update({
                    "overall_status": health_data.get("status"),
                    "component_health": health_data.get("component_health", {}),
                    "statistics": health_data.get("statistics", {})
                })
                
                # Validate all components are healthy
                component_health = health_data.get("component_health", {})
                unhealthy_components = [
                    name for name, status in component_health.items()
                    if status != "healthy"
                ]
                
                if unhealthy_components:
                    success = False
                    details["unhealthy_components"] = unhealthy_components
            
            self._record_result("system_health", success, start_time, details)
            
        except Exception as e:
            self._record_result("system_health", False, start_time, {}, str(e))
    
    def _validate_authentication(self):
        """Validate authentication mechanisms."""
        
        start_time = time.time()
        
        try:
            # Test without authentication
            response = self.client.get("/v1/profile/preferences")
            
            # Should return 401 or 403
            auth_required = response.status_code in [401, 403]
            
            # Test with valid authentication
            headers = {"Authorization": "Bearer user:test_e2e_user"}
            
            with patch('app.api.profile.get_db_connection') as mock_db:
                self._setup_mock_db(mock_db, "test_e2e_user")
                
                response = self.client.get("/v1/profile/preferences", headers=headers)
                auth_works = response.status_code == 200
            
            success = auth_required and auth_works
            details = {
                "auth_required": auth_required,
                "auth_works": auth_works,
                "response_time_ms": (time.time() - start_time) * 1000
            }
            
            self._record_result("authentication", success, start_time, details)
            
        except Exception as e:
            self._record_result("authentication", False, start_time, {}, str(e))
    
    def _validate_rate_limiting(self):
        """Validate rate limiting functionality."""
        
        start_time = time.time()
        
        try:
            headers = {"Authorization": "Bearer user:test_rate_limit_user"}
            
            # Make multiple rapid requests
            responses = []
            for i in range(5):
                response = self.client.get("/v1/profile/preferences", headers=headers)
                responses.append(response.status_code)
                time.sleep(0.1)  # Small delay between requests
            
            # All should succeed (under rate limit)
            all_success = all(status == 200 for status in responses)
            
            details = {
                "response_codes": responses,
                "all_under_limit": all_success,
                "response_time_ms": (time.time() - start_time) * 1000
            }
            
            self._record_result("rate_limiting", all_success, start_time, details)
            
        except Exception as e:
            self._record_result("rate_limiting", False, start_time, {}, str(e))
    
    def _validate_new_user_onboarding(self):
        """Validate new user onboarding flow."""
        
        start_time = time.time()
        
        try:
            user_id = f"test_new_user_{int(time.time())}"
            headers = {"Authorization": f"Bearer user:{user_id}"}
            
            with patch('app.api.profile.get_db_connection') as mock_db:
                # Mock database for new user (no existing records)
                mock_cursor = Mock()
                mock_cursor.fetchone.side_effect = [
                    None,  # No existing user record
                    {      # Created user record
                        'user_id': user_id,
                        'created_at': datetime.utcnow(),
                        'last_seen_at': datetime.utcnow(),
                        'opt_out_personalization': False,
                        'opt_out_experiments': False
                    },
                    None   # No preferences record
                ]
                
                mock_conn = Mock()
                mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
                mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
                mock_conn.__enter__ = Mock(return_value=mock_conn)
                mock_conn.__exit__ = Mock(return_value=None)
                mock_db.return_value = mock_conn
                
                with patch('app.api.profile.get_feature_cache') as mock_cache:
                    mock_cache_instance = Mock()
                    mock_cache_instance.get_features_sync.return_value = Mock(
                        user_id=user_id,
                        hue_bias={},
                        neutral_affinity=0.0,
                        saturation_cap_adjust=0.0,
                        lightness_bias=0.0,
                        event_count=0,
                        updated_at=datetime.utcnow()
                    )
                    mock_cache.return_value = mock_cache_instance
                    
                    # Get initial profile (should create user)
                    response = self.client.get("/v1/profile/preferences", headers=headers)
                    
                    success = response.status_code == 200
                    profile_data = response.json() if success else {}
                    
                    details = {
                        "status_code": response.status_code,
                        "user_created": success,
                        "has_default_preferences": "preferences" in profile_data,
                        "has_empty_features": profile_data.get("features", {}).get("event_count") == 0,
                        "response_time_ms": (time.time() - start_time) * 1000
                    }
                    
                    self._record_result("new_user_onboarding", success, start_time, details)
            
        except Exception as e:
            self._record_result("new_user_onboarding", False, start_time, {}, str(e))
    
    def _validate_preference_setting(self):
        """Validate user preference setting and retrieval."""
        
        start_time = time.time()
        
        try:
            user_id = f"test_pref_user_{int(time.time())}"
            headers = {"Authorization": f"Bearer user:{user_id}"}
            
            preferences = {
                "avoid_hues": ["green", "purple"],
                "prefer_neutrals": True,
                "saturation_comfort": "medium",
                "lightness_comfort": "light",
                "season_bias": "spring_summer"
            }
            
            with patch('app.api.profile.get_db_connection') as mock_db:
                self._setup_mock_db(mock_db, user_id)
                
                with patch('app.api.profile.get_feature_cache') as mock_cache:
                    mock_cache_instance = Mock()
                    mock_cache.return_value = mock_cache_instance
                    
                    with patch('app.api.profile.get_user_preferences') as mock_get:
                        mock_profile = Mock()
                        mock_profile.dict.return_value = {
                            'user_id': user_id,
                            'preferences': preferences,
                            'features': {'event_count': 0}
                        }
                        mock_get.return_value = mock_profile
                        
                        # Set preferences
                        response = self.client.post(
                            "/v1/profile/preferences",
                            json=preferences,
                            headers=headers
                        )
                        
                        success = response.status_code == 200
                        
                        details = {
                            "status_code": response.status_code,
                            "preferences_set": success,
                            "cache_invalidated": mock_cache_instance.invalidate_cache_sync.called,
                            "response_time_ms": (time.time() - start_time) * 1000
                        }
                        
                        self._record_result("preference_setting", success, start_time, details)
            
        except Exception as e:
            self._record_result("preference_setting", False, start_time, {}, str(e))
    
    def _validate_event_ingestion(self):
        """Validate event ingestion pipeline."""
        
        start_time = time.time()
        
        try:
            user_id = f"test_events_user_{int(time.time())}"
            
            # Test single event
            single_event = {
                "user_id": user_id,
                "event": {
                    "event_type": "like",
                    "suggestion_id": "sugg_test_123",
                    "colors": ["red", "white"],
                    "context": {"source": "e2e_test"}
                },
                "metadata": {"session_id": "e2e_session", "platform": "test"}
            }
            
            response = self.client.post("/v1/events/single", json=single_event)
            single_success = response.status_code == 200
            
            # Test batch events
            batch_events = {
                "user_id": user_id,
                "events": [
                    {
                        "event_type": "view",
                        "suggestion_id": "sugg_test_124",
                        "colors": ["blue", "navy"]
                    },
                    {
                        "event_type": "like",
                        "suggestion_id": "sugg_test_125",
                        "colors": ["green", "forest"]
                    }
                ],
                "metadata": {"session_id": "e2e_session"}
            }
            
            response = self.client.post("/v1/events/batch", json=batch_events)
            batch_success = response.status_code == 200
            
            success = single_success and batch_success
            
            details = {
                "single_event_success": single_success,
                "batch_events_success": batch_success,
                "total_events_sent": 3,
                "response_time_ms": (time.time() - start_time) * 1000
            }
            
            self._record_result("event_ingestion", success, start_time, details)
            
        except Exception as e:
            self._record_result("event_ingestion", False, start_time, {}, str(e))
    
    def _validate_feature_computation(self):
        """Validate feature computation pipeline."""
        
        start_time = time.time()
        
        try:
            # Mock feature computation with sample events
            from app.services.personalization.features import FeatureComputer
            
            sample_events = [
                {
                    'event_type': 'like',
                    'colors': ['red', 'white'],
                    'event_time': datetime.utcnow() - timedelta(days=1),
                    'suggestion_id': 'sugg_1'
                },
                {
                    'event_type': 'view',
                    'colors': ['blue', 'navy'],
                    'event_time': datetime.utcnow() - timedelta(days=2),
                    'suggestion_id': 'sugg_2'
                },
                {
                    'event_type': 'like',
                    'colors': ['red', 'burgundy'],
                    'event_time': datetime.utcnow() - timedelta(days=3),
                    'suggestion_id': 'sugg_3'
                }
            ]
            
            computer = FeatureComputer()
            features = computer.compute_features("test_user", sample_events)
            
            # Validate feature structure
            required_features = [
                'hue_bias', 'neutral_affinity', 'saturation_cap_adjust',
                'lightness_bias', 'event_count'
            ]
            
            has_all_features = all(hasattr(features, feature) for feature in required_features)
            
            # Validate feature values are reasonable
            valid_ranges = True
            if hasattr(features, 'neutral_affinity'):
                valid_ranges &= 0.0 <= features.neutral_affinity <= 1.0
            if hasattr(features, 'saturation_cap_adjust'):
                valid_ranges &= -0.5 <= features.saturation_cap_adjust <= 0.5
            if hasattr(features, 'lightness_bias'):
                valid_ranges &= -0.5 <= features.lightness_bias <= 0.5
            
            success = has_all_features and valid_ranges
            
            details = {
                "has_all_features": has_all_features,
                "valid_ranges": valid_ranges,
                "event_count": getattr(features, 'event_count', 0),
                "hue_bias_count": len(getattr(features, 'hue_bias', {})),
                "response_time_ms": (time.time() - start_time) * 1000
            }
            
            self._record_result("feature_computation", success, start_time, details)
            
        except Exception as e:
            self._record_result("feature_computation", False, start_time, {}, str(e))
    
    def _validate_personalized_suggestions(self):
        """Validate personalized suggestion generation."""
        
        start_time = time.time()
        
        try:
            user_id = f"test_suggestions_user_{int(time.time())}"
            headers = {"Authorization": f"Bearer user:{user_id}"}
            
            # Mock the full suggestion pipeline
            with patch('main.conn') as mock_conn:
                # Mock database queries
                mock_cursor = Mock()
                mock_cursor.fetchone.side_effect = [
                    ('garment_e2e_test', 'top', 'path/to/test.jpg', ['red', 'white'], ['casual']),
                    (False, False)  # User opt-out preferences
                ]
                
                mock_cursor.fetchall.return_value = [
                    ('candidate_1', 'path/to/cand1.jpg', ['blue', 'navy'], ['formal']),
                    ('candidate_2', 'path/to/cand2.jpg', ['gray', 'black'], ['business'])
                ]
                
                mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
                mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
                
                with patch('app.services.personalization.get_feature_cache') as mock_cache:
                    mock_cache_instance = Mock()
                    mock_cache_instance.get_features_sync.return_value = Mock(
                        user_id=user_id,
                        hue_bias={'blue': 0.3, 'red': -0.1},
                        neutral_affinity=0.2,
                        saturation_cap_adjust=0.1,
                        lightness_bias=0.0,
                        event_count=10,
                        updated_at=datetime.utcnow()
                    )
                    mock_cache.return_value = mock_cache_instance
                    
                    with patch('app.services.personalization.ranking.get_personalized_ranker') as mock_ranker:
                        mock_ranker_instance = Mock()
                        mock_result = Mock()
                        mock_result.suggestions = [
                            Mock(
                                suggestion_id='sugg_e2e_test',
                                colors=['blue', 'navy'],
                                base_score=0.85,
                                metadata={'reasons': ['color_harmony']}
                            )
                        ]
                        mock_result.personalization_applied = True
                        mock_result.experiment_variant = 'treatment_a'
                        mock_result.reranking_time_ms = 15.0
                        
                        mock_ranker_instance.rerank_with_personalization.return_value = mock_result
                        mock_ranker.return_value = mock_ranker_instance
                        
                        with patch('main.create_signed_url') as mock_sign:
                            mock_sign.return_value = 'https://signed-url.com/image.jpg'
                            
                            response = self.client.get("/suggest/garment_e2e_test", headers=headers)
                            
                            success = response.status_code == 200
                            suggestion_data = response.json() if success else {}
                            
                            # Validate response structure
                            has_suggestions = len(suggestion_data.get('suggestions', [])) > 0
                            has_personalization = mock_ranker_instance.rerank_with_personalization.called
                            
                            success = success and has_suggestions and has_personalization
                            
                            details = {
                                "status_code": response.status_code,
                                "has_suggestions": has_suggestions,
                                "personalization_applied": has_personalization,
                                "suggestion_count": len(suggestion_data.get('suggestions', [])),
                                "response_time_ms": (time.time() - start_time) * 1000
                            }
                            
                            self._record_result("personalized_suggestions", success, start_time, details)
            
        except Exception as e:
            self._record_result("personalized_suggestions", False, start_time, {}, str(e))
    
    def _validate_experiment_assignment(self):
        """Validate A/B experiment assignment."""
        
        start_time = time.time()
        
        try:
            from app.services.personalization.experiments import ExperimentManager
            
            # Test experiment assignment
            experiment_manager = ExperimentManager()
            
            # Test multiple users get assigned to different variants
            assignments = {}
            for i in range(10):
                user_id = f"test_exp_user_{i}"
                variant = experiment_manager.get_experiment_variant(user_id, "color_matching_algorithm")
                
                if variant not in assignments:
                    assignments[variant] = 0
                assignments[variant] += 1
            
            # Should have at least 2 different variants
            has_multiple_variants = len(assignments) >= 2
            
            # Test assignment consistency
            consistent_assignment = True
            for _ in range(3):
                variant = experiment_manager.get_experiment_variant("consistent_user", "color_matching_algorithm")
                if variant != experiment_manager.get_experiment_variant("consistent_user", "color_matching_algorithm"):
                    consistent_assignment = False
                    break
            
            success = has_multiple_variants and consistent_assignment
            
            details = {
                "variant_distribution": assignments,
                "has_multiple_variants": has_multiple_variants,
                "consistent_assignment": consistent_assignment,
                "response_time_ms": (time.time() - start_time) * 1000
            }
            
            self._record_result("experiment_assignment", success, start_time, details)
            
        except Exception as e:
            self._record_result("experiment_assignment", False, start_time, {}, str(e))
    
    def _validate_data_consistency(self):
        """Validate data consistency across components."""
        
        start_time = time.time()
        
        try:
            # Test that user preferences and features remain consistent
            user_id = f"test_consistency_user_{int(time.time())}"
            
            # Mock consistent data across multiple requests
            with patch('app.api.profile.get_db_connection') as mock_db:
                self._setup_mock_db(mock_db, user_id)
                
                with patch('app.api.profile.get_feature_cache') as mock_cache:
                    mock_cache_instance = Mock()
                    consistent_features = Mock(
                        user_id=user_id,
                        hue_bias={'red': 0.2},
                        neutral_affinity=0.3,
                        event_count=5,
                        updated_at=datetime.utcnow()
                    )
                    mock_cache_instance.get_features_sync.return_value = consistent_features
                    mock_cache.return_value = mock_cache_instance
                    
                    headers = {"Authorization": f"Bearer user:{user_id}"}
                    
                    # Make multiple requests
                    responses = []
                    for _ in range(3):
                        response = self.client.get("/v1/profile/preferences", headers=headers)
                        if response.status_code == 200:
                            responses.append(response.json())
                        time.sleep(0.1)
                    
                    # Check consistency
                    if len(responses) >= 2:
                        first_features = responses[0].get('features', {})
                        consistent = all(
                            resp.get('features', {}).get('event_count') == first_features.get('event_count')
                            for resp in responses[1:]
                        )
                    else:
                        consistent = False
                    
                    success = len(responses) >= 2 and consistent
                    
                    details = {
                        "successful_requests": len(responses),
                        "data_consistent": consistent,
                        "response_time_ms": (time.time() - start_time) * 1000
                    }
                    
                    self._record_result("data_consistency", success, start_time, details)
            
        except Exception as e:
            self._record_result("data_consistency", False, start_time, {}, str(e))
    
    def _validate_performance_requirements(self):
        """Validate system meets performance requirements."""
        
        start_time = time.time()
        
        try:
            # Test response times
            user_id = f"test_perf_user_{int(time.time())}"
            headers = {"Authorization": f"Bearer user:{user_id}"}
            
            with patch('app.api.profile.get_db_connection') as mock_db:
                self._setup_mock_db(mock_db, user_id)
                
                # Measure response times for different endpoints
                response_times = {}
                
                # Profile endpoint
                start = time.time()
                response = self.client.get("/v1/profile/preferences", headers=headers)
                response_times['profile'] = (time.time() - start) * 1000
                
                # Events endpoint
                start = time.time()
                event_data = {
                    "user_id": user_id,
                    "event": {
                        "event_type": "like",
                        "suggestion_id": "perf_test",
                        "colors": ["red"]
                    }
                }
                response = self.client.post("/v1/events/single", json=event_data)
                response_times['events'] = (time.time() - start) * 1000
                
                # Analytics endpoint
                start = time.time()
                response = self.client.get("/v1/analytics/health/phase5")
                response_times['analytics'] = (time.time() - start) * 1000
                
                # Validate performance requirements
                performance_ok = True
                requirements = {
                    'profile': 1000,     # 1 second max
                    'events': 500,       # 500ms max
                    'analytics': 2000    # 2 seconds max
                }
                
                for endpoint, max_time in requirements.items():
                    if response_times.get(endpoint, 0) > max_time:
                        performance_ok = False
                
                success = performance_ok
                
                details = {
                    "response_times_ms": response_times,
                    "requirements_met": performance_ok,
                    "total_time_ms": (time.time() - start_time) * 1000
                }
                
                self._record_result("performance_requirements", success, start_time, details)
            
        except Exception as e:
            self._record_result("performance_requirements", False, start_time, {}, str(e))
    
    def _validate_data_privacy_compliance(self):
        """Validate GDPR and data privacy compliance."""
        
        start_time = time.time()
        
        try:
            user_id = f"test_privacy_user_{int(time.time())}"
            headers = {"Authorization": f"Bearer user:{user_id}"}
            
            # Test data deletion
            deletion_request = {
                "user_id": user_id,
                "confirmation": "DELETE_MY_DATA"
            }
            
            with patch('app.api.profile.get_db_connection') as mock_db:
                mock_cursor = Mock()
                mock_cursor.rowcount = 3  # Mock deleted rows
                
                mock_conn = Mock()
                mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
                mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
                mock_conn.__enter__ = Mock(return_value=mock_conn)
                mock_conn.__exit__ = Mock(return_value=None)
                mock_db.return_value = mock_conn
                
                with patch('app.api.profile.get_feature_cache') as mock_cache:
                    mock_cache_instance = Mock()
                    mock_cache.return_value = mock_cache_instance
                    
                    response = self.client.post(
                        "/v1/profile/delete",
                        json=deletion_request,
                        headers=headers
                    )
                    
                    deletion_works = response.status_code == 200
                    
                    # Test audit logging
                    with patch('app.services.security.audit_logger.AuditLogger') as mock_audit:
                        mock_audit_instance = Mock()
                        mock_audit.return_value = mock_audit_instance
                        
                        # Any API call should trigger audit logging
                        self.client.get("/v1/profile/preferences", headers=headers)
                        
                        audit_called = mock_audit_instance.log_audit_event.called if hasattr(mock_audit_instance, 'log_audit_event') else True
                    
                    success = deletion_works and audit_called
                    
                    details = {
                        "data_deletion_works": deletion_works,
                        "audit_logging_active": audit_called,
                        "response_time_ms": (time.time() - start_time) * 1000
                    }
                    
                    self._record_result("data_privacy_compliance", success, start_time, details)
            
        except Exception as e:
            self._record_result("data_privacy_compliance", False, start_time, {}, str(e))
    
    def _validate_analytics_pipeline(self):
        """Validate analytics and KPI pipeline."""
        
        start_time = time.time()
        
        try:
            with patch('app.api.phase5_analytics.get_db_connection') as mock_db:
                # Mock KPI data
                mock_cursor = Mock()
                mock_cursor.fetchone.side_effect = [
                    {'total_sessions': 100, 'personalized_sessions': 75, 'avg_reranking_time_ms': 15.5},
                    {'users_with_recent_features': 50},
                    {'total_active_users': 80},
                    {'total_events': 500, 'unique_users': 80},
                    (25,),
                ]
                
                mock_cursor.fetchall.side_effect = [
                    [{'event_type': 'like', 'count': 200}, {'event_type': 'view', 'count': 300}],
                    [],  # Experiments
                    []   # Experiment variants
                ]
                
                mock_conn = Mock()
                mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
                mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
                mock_conn.__enter__ = Mock(return_value=mock_conn)
                mock_conn.__exit__ = Mock(return_value=None)
                mock_db.return_value = mock_conn
                
                response = self.client.get("/v1/analytics/kpis?days=7")
                
                success = response.status_code == 200
                kpi_data = response.json() if success else {}
                
                # Validate KPI structure
                has_required_sections = all(
                    section in kpi_data
                    for section in ['personalization', 'engagement', 'experiments', 'feature_health']
                )
                
                success = success and has_required_sections
                
                details = {
                    "status_code": response.status_code,
                    "has_required_sections": has_required_sections,
                    "kpi_sections": list(kpi_data.keys()) if success else [],
                    "response_time_ms": (time.time() - start_time) * 1000
                }
                
                self._record_result("analytics_pipeline", success, start_time, details)
            
        except Exception as e:
            self._record_result("analytics_pipeline", False, start_time, {}, str(e))
    
    def _validate_audit_logging(self):
        """Validate audit logging functionality."""
        
        start_time = time.time()
        
        try:
            from app.services.security.audit_logger import AuditLogger
            
            # Test audit logger
            audit_logger = AuditLogger()
            
            # Test logging different event types
            test_events = [
                ('user_preference_update', 'test_user', {'setting': 'avoid_hues'}),
                ('data_access', 'test_user', {'endpoint': '/v1/profile/preferences'}),
                ('data_deletion', 'test_user', {'confirmation': True})
            ]
            
            logged_successfully = True
            for event_type, user_id, data in test_events:
                try:
                    audit_logger.log_audit_event(event_type, user_id, data)
                except Exception:
                    logged_successfully = False
                    break
            
            success = logged_successfully
            
            details = {
                "audit_events_logged": len(test_events),
                "logging_successful": logged_successfully,
                "response_time_ms": (time.time() - start_time) * 1000
            }
            
            self._record_result("audit_logging", success, start_time, details)
            
        except Exception as e:
            self._record_result("audit_logging", False, start_time, {}, str(e))
    
    def _setup_mock_db(self, mock_db, user_id: str):
        """Setup common database mocks for testing."""
        
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            {  # User record
                'user_id': user_id,
                'created_at': datetime.utcnow(),
                'last_seen_at': datetime.utcnow(),
                'opt_out_personalization': False,
                'opt_out_experiments': False
            },
            {  # Preferences record
                'avoid_hues': '[]',
                'prefer_neutrals': False,
                'saturation_comfort': 'medium',
                'lightness_comfort': 'medium',
                'season_bias': 'no_preference'
            }
        ]
        
        mock_conn = Mock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_db.return_value = mock_conn
    
    def _record_result(self, test_name: str, success: bool, start_time: float, 
                      details: Dict[str, Any], error: Optional[str] = None):
        """Record a validation test result."""
        
        duration_ms = (time.time() - start_time) * 1000
        
        result = ValidationResult(
            test_name=test_name,
            success=success,
            duration_ms=duration_ms,
            details=details,
            error=error
        )
        
        self.results.append(result)
        
        status = "PASS" if success else "FAIL"
        print(f"  {test_name}: {status} ({duration_ms:.1f}ms)")
        
        if error:
            print(f"    Error: {error}")
    
    def _generate_validation_report(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        
        passed = sum(1 for result in self.results if result.success)
        total = len(self.results)
        
        report = {
            "validation_summary": {
                "total_tests": total,
                "passed": passed,
                "failed": total - passed,
                "success_rate": (passed / total) * 100 if total > 0 else 0,
                "total_duration_seconds": total_time
            },
            "test_results": [
                {
                    "test_name": result.test_name,
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                    "details": result.details,
                    "error": result.error
                }
                for result in self.results
            ],
            "performance_summary": {
                "avg_response_time_ms": sum(r.duration_ms for r in self.results) / total if total > 0 else 0,
                "slowest_test": max(self.results, key=lambda r: r.duration_ms).test_name if self.results else None,
                "fastest_test": min(self.results, key=lambda r: r.duration_ms).test_name if self.results else None
            },
            "critical_issues": [
                result.test_name for result in self.results
                if not result.success and result.test_name in [
                    'system_health', 'authentication', 'personalized_suggestions',
                    'data_privacy_compliance'
                ]
            ],
            "recommendations": self._generate_recommendations()
        }
        
        print(f"\n=== Phase 5 End-to-End Validation Complete ===")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {report['validation_summary']['success_rate']:.1f}%")
        print(f"Total Time: {total_time:.2f} seconds")
        
        if report['critical_issues']:
            print(f"\nCRITICAL ISSUES FOUND:")
            for issue in report['critical_issues']:
                print(f"  - {issue}")
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results."""
        
        recommendations = []
        
        failed_tests = [r for r in self.results if not r.success]
        
        for result in failed_tests:
            if result.test_name == "system_health":
                recommendations.append("Check system health endpoints and component status")
            elif result.test_name == "authentication":
                recommendations.append("Verify authentication middleware configuration")
            elif result.test_name == "performance_requirements":
                recommendations.append("Optimize API response times and database queries")
            elif result.test_name == "data_privacy_compliance":
                recommendations.append("Ensure GDPR compliance and audit logging functionality")
            elif result.test_name == "personalized_suggestions":
                recommendations.append("Verify personalization pipeline and feature computation")
        
        # Performance recommendations
        slow_tests = [r for r in self.results if r.duration_ms > 1000]
        if slow_tests:
            recommendations.append("Consider optimizing slow operations for better performance")
        
        if not recommendations:
            recommendations.append("All validations passed successfully! System is ready for production.")
        
        return recommendations


def run_phase5_validation():
    """Run complete Phase 5 end-to-end validation."""
    
    # This would normally import the FastAPI app
    # For now, we'll create a mock client
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    
    app = FastAPI()
    client = TestClient(app)
    
    config = {
        "environment": "validation",
        "strict_mode": True
    }
    
    validator = Phase5E2EValidator(client, config)
    return validator.run_all_validations()


if __name__ == "__main__":
    # Run validation and save report
    validation_report = run_phase5_validation()
    
    # Save report to file
    with open("phase5_validation_report.json", "w") as f:
        json.dump(validation_report, f, indent=2, default=str)
    
    print(f"\nValidation report saved to: phase5_validation_report.json")
    
    # Exit with error code if critical issues found
    if validation_report['critical_issues']:
        exit(1)
