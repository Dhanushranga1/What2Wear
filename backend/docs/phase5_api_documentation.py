"""
Phase 5 Personalization API Documentation
Generated OpenAPI specification with authentication and rate limiting examples.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field


# Request/Response Models for Documentation
class UserPreferences(BaseModel):
    """User preference settings for personalization."""
    avoid_hues: List[str] = Field(
        default=[],
        description="Hue names to avoid in suggestions",
        example=["green", "purple"]
    )
    prefer_neutrals: bool = Field(
        default=False,
        description="Whether user prefers neutral colors",
        example=True
    )
    saturation_comfort: str = Field(
        default="medium",
        description="Preferred saturation level",
        example="medium",
        regex="^(low|medium|high)$"
    )
    lightness_comfort: str = Field(
        default="medium",
        description="Preferred lightness level",
        example="light",
        regex="^(dark|medium|light)$"
    )
    season_bias: str = Field(
        default="no_preference",
        description="Seasonal color preference",
        example="spring_summer",
        regex="^(spring_summer|autumn_winter|no_preference)$"
    )


class UserFeatures(BaseModel):
    """Computed personalization features for a user."""
    hue_bias: Dict[str, float] = Field(
        description="Bias scores for different hues (-1 to 1)",
        example={"red": 0.3, "blue": -0.1, "green": 0.0}
    )
    neutral_affinity: float = Field(
        description="Preference for neutral colors (0 to 1)",
        example=0.4,
        ge=0,
        le=1
    )
    saturation_cap_adjust: float = Field(
        description="Saturation preference adjustment (-0.5 to 0.5)",
        example=0.1,
        ge=-0.5,
        le=0.5
    )
    lightness_bias: float = Field(
        description="Lightness preference bias (-0.5 to 0.5)",
        example=-0.2,
        ge=-0.5,
        le=0.5
    )
    event_count: int = Field(
        description="Total events used to compute features",
        example=45,
        ge=0
    )
    updated_at: datetime = Field(
        description="When features were last updated",
        example="2024-01-15T10:30:00Z"
    )


class UserProfile(BaseModel):
    """Complete user profile with preferences and features."""
    user_id: str = Field(description="Unique user identifier", example="user_123456")
    preferences: UserPreferences
    features: UserFeatures
    created_at: datetime = Field(example="2024-01-01T00:00:00Z")
    last_seen_at: datetime = Field(example="2024-01-15T12:00:00Z")


class Event(BaseModel):
    """User interaction event."""
    event_type: str = Field(
        description="Type of interaction",
        example="like",
        regex="^(view|like|dislike|purchase|share)$"
    )
    suggestion_id: str = Field(
        description="ID of the suggestion interacted with",
        example="sugg_garment_123_456"
    )
    colors: List[str] = Field(
        description="Colors involved in the interaction",
        example=["red", "white", "blue"]
    )
    context: Dict[str, Any] = Field(
        default={},
        description="Additional context about the event",
        example={"source": "outfit_suggestions", "position": 2}
    )


class SingleEventRequest(BaseModel):
    """Request to ingest a single event."""
    user_id: str = Field(description="User performing the action", example="user_123456")
    event: Event
    metadata: Dict[str, Any] = Field(
        default={},
        description="Session and platform metadata",
        example={"session_id": "sess_789", "platform": "web"}
    )


class BatchEventRequest(BaseModel):
    """Request to ingest multiple events."""
    user_id: str = Field(description="User performing the actions", example="user_123456")
    events: List[Event] = Field(description="List of events to ingest")
    metadata: Dict[str, Any] = Field(
        default={},
        description="Session and platform metadata",
        example={"session_id": "sess_789", "platform": "web"}
    )


class EventResponse(BaseModel):
    """Response after event ingestion."""
    status: str = Field(description="Ingestion status", example="accepted")
    event_id: str = Field(description="Generated event ID", example="evt_123456789")
    timestamp: datetime = Field(description="Event timestamp", example="2024-01-15T12:00:00Z")


class BatchEventResponse(BaseModel):
    """Response after batch event ingestion."""
    status: str = Field(description="Ingestion status", example="accepted")
    event_count: int = Field(description="Number of events processed", example=5)
    event_ids: List[str] = Field(
        description="Generated event IDs",
        example=["evt_123456789", "evt_123456790"]
    )
    timestamp: datetime = Field(description="Batch processing timestamp")


class PersonalizationKPIs(BaseModel):
    """Personalization system KPIs."""
    total_sessions: int = Field(description="Total user sessions", example=1000)
    personalized_sessions: int = Field(description="Sessions with personalization", example=750)
    personalization_rate: float = Field(description="Percentage of personalized sessions", example=75.0)
    avg_reranking_time_ms: float = Field(description="Average reranking latency", example=15.5)


class EngagementKPIs(BaseModel):
    """User engagement KPIs."""
    total_events: int = Field(description="Total user events", example=5000)
    unique_users: int = Field(description="Unique active users", example=200)
    avg_events_per_user: float = Field(description="Average events per user", example=25.0)
    event_breakdown: Dict[str, int] = Field(
        description="Events by type",
        example={"like": 2000, "view": 2500, "dislike": 300, "purchase": 200}
    )


class ExperimentKPIs(BaseModel):
    """A/B experiment KPIs."""
    active_experiments: int = Field(description="Number of active experiments", example=3)
    users_in_experiments: int = Field(description="Users participating in experiments", example=150)
    experiments: List[Dict[str, Any]] = Field(
        description="Experiment details",
        example=[
            {
                "experiment_id": "exp_001",
                "name": "New Ranking Algorithm",
                "status": "active",
                "variants": {"control": 0.5, "treatment": 0.5}
            }
        ]
    )


class OverallKPIs(BaseModel):
    """Complete KPI dashboard."""
    period_days: int = Field(description="Analysis period in days", example=7)
    generated_at: datetime = Field(description="Report generation time")
    personalization: PersonalizationKPIs
    engagement: EngagementKPIs
    experiments: ExperimentKPIs
    feature_health: Dict[str, Any] = Field(
        description="Feature computation health metrics",
        example={
            "users_with_recent_features": 180,
            "avg_feature_age_hours": 6.5,
            "feature_coverage_rate": 90.0
        }
    )


class HealthStatus(BaseModel):
    """System health status."""
    status: str = Field(description="Overall health status", example="healthy")
    timestamp: datetime = Field(description="Health check timestamp")
    component_health: Dict[str, str] = Field(
        description="Health of individual components",
        example={
            "events_pipeline": "healthy",
            "feature_computation": "healthy",
            "ranking_service": "healthy",
            "experiments": "healthy"
        }
    )
    statistics: Dict[str, Any] = Field(
        description="Current system statistics",
        example={
            "events_last_hour": 50,
            "sessions_last_hour": 30,
            "features_updated_24h": 200,
            "active_experiments": 2
        }
    )


class DataDeletionRequest(BaseModel):
    """Request to delete user data."""
    user_id: str = Field(description="User ID to delete data for", example="user_123456")
    confirmation: str = Field(
        description="Confirmation string",
        example="DELETE_MY_DATA",
        regex="^DELETE_MY_DATA$"
    )


class DataDeletionResponse(BaseModel):
    """Response after data deletion."""
    status: str = Field(description="Deletion status", example="success")
    user_id: str = Field(description="User ID deleted", example="user_123456")
    deleted_records: Dict[str, int] = Field(
        description="Count of deleted records by table",
        example={
            "user_preferences": 1,
            "user_events": 45,
            "user_features": 1,
            "user_experiments": 2
        }
    )
    timestamp: datetime = Field(description="Deletion timestamp")


# Custom OpenAPI Schema
def get_phase5_openapi():
    """Generate custom OpenAPI schema for Phase 5 APIs."""
    
    openapi_schema = {
        "openapi": "3.0.2",
        "info": {
            "title": "What2Wear Phase 5 Personalization API",
            "version": "1.0.0",
            "description": """
## Phase 5 Personalization System

This API provides endpoints for the Phase 5 personalization system including:

- **Profile Management**: User preferences and feature access
- **Event Ingestion**: User interaction tracking 
- **Analytics**: KPIs and system health monitoring

### Authentication

All endpoints require authentication via Bearer token in the Authorization header:

```
Authorization: Bearer user:your_user_id_here
```

### Rate Limiting

API requests are rate limited by endpoint category:

- **Profile endpoints**: 60 requests per minute per user
- **Event endpoints**: 1000 requests per minute per user  
- **Analytics endpoints**: 100 requests per minute per user

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Time until reset (Unix timestamp)

### Error Handling

Standard HTTP status codes are used:

- `200`: Success
- `400`: Bad Request (invalid input)
- `401`: Unauthorized (invalid token)
- `403`: Forbidden (missing token)
- `422`: Unprocessable Entity (validation error)
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error

Error responses include details:

```json
{
    "error": "validation_error",
    "message": "Invalid saturation_comfort value",
    "details": {
        "field": "saturation_comfort",
        "allowed_values": ["low", "medium", "high"]
    }
}
```

### Data Privacy

This API complies with GDPR and provides:

- Data export via `/v1/profile/preferences`
- Data deletion via `/v1/profile/delete`
- Audit logging of all data access
- Optional encryption for PII fields
            """,
            "contact": {
                "name": "What2Wear API Support",
                "email": "api-support@what2wear.com"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        },
        "servers": [
            {
                "url": "https://api.what2wear.com",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.what2wear.com", 
                "description": "Staging server"
            },
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Bearer token authentication. Format: `Bearer user:your_user_id`"
                }
            },
            "responses": {
                "UnauthorizedError": {
                    "description": "Authentication information is missing or invalid",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "error": {"type": "string", "example": "unauthorized"},
                                    "message": {"type": "string", "example": "Invalid or missing authentication token"}
                                }
                            }
                        }
                    }
                },
                "RateLimitError": {
                    "description": "Too many requests",
                    "headers": {
                        "X-RateLimit-Limit": {
                            "description": "Request limit per window",
                            "schema": {"type": "integer"}
                        },
                        "X-RateLimit-Remaining": {
                            "description": "Remaining requests",
                            "schema": {"type": "integer"}
                        },
                        "X-RateLimit-Reset": {
                            "description": "Time until reset (Unix timestamp)",
                            "schema": {"type": "integer"}
                        }
                    },
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "error": {"type": "string", "example": "rate_limit_exceeded"},
                                    "message": {"type": "string", "example": "Too many requests. Try again later."}
                                }
                            }
                        }
                    }
                }
            }
        },
        "security": [
            {"BearerAuth": []}
        ],
        "paths": {
            "/v1/profile/preferences": {
                "get": {
                    "tags": ["Profile Management"],
                    "summary": "Get user preferences and features",
                    "description": "Retrieve the complete user profile including preferences and computed personalization features.",
                    "responses": {
                        "200": {
                            "description": "User profile retrieved successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserProfile"}
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                },
                "post": {
                    "tags": ["Profile Management"],
                    "summary": "Update user preferences",
                    "description": "Update user personalization preferences. This will invalidate cached features and trigger recomputation.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UserPreferences"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Preferences updated successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserProfile"}
                                }
                            }
                        },
                        "422": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "error": {"type": "string"},
                                            "message": {"type": "string"},
                                            "details": {"type": "object"}
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                }
            },
            "/v1/profile/delete": {
                "post": {
                    "tags": ["Profile Management"],
                    "summary": "Delete user data",
                    "description": "Permanently delete all user data including preferences, events, and features. This action cannot be undone.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DataDeletionRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Data deleted successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/DataDeletionResponse"}
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                }
            },
            "/v1/events/single": {
                "post": {
                    "tags": ["Event Ingestion"],
                    "summary": "Ingest a single user event",
                    "description": "Record a single user interaction event for personalization.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SingleEventRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Event ingested successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/EventResponse"}
                                }
                            }
                        },
                        "422": {
                            "description": "Invalid event data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "error": {"type": "string"},
                                            "message": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                }
            },
            "/v1/events/batch": {
                "post": {
                    "tags": ["Event Ingestion"],
                    "summary": "Ingest multiple user events",
                    "description": "Record multiple user interaction events in a single request for efficiency.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/BatchEventRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Events ingested successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/BatchEventResponse"}
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                }
            },
            "/v1/events/health": {
                "get": {
                    "tags": ["Event Ingestion"],
                    "summary": "Event pipeline health check",
                    "description": "Check the health and throughput of the event ingestion pipeline.",
                    "responses": {
                        "200": {
                            "description": "Pipeline health status",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "example": "healthy"},
                                            "events_last_hour": {"type": "integer", "example": 1500},
                                            "events_last_5min": {"type": "integer", "example": 25},
                                            "avg_ingestion_time_ms": {"type": "number", "example": 5.2}
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                }
            },
            "/v1/analytics/kpis": {
                "get": {
                    "tags": ["Analytics"],
                    "summary": "Get overall system KPIs",
                    "description": "Retrieve comprehensive KPIs for personalization, engagement, and experiments.",
                    "parameters": [
                        {
                            "name": "days",
                            "in": "query",
                            "description": "Number of days to analyze",
                            "required": False,
                            "schema": {"type": "integer", "default": 7, "minimum": 1, "maximum": 90}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "KPI data retrieved successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/OverallKPIs"}
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                }
            },
            "/v1/analytics/health/phase5": {
                "get": {
                    "tags": ["Analytics"],
                    "summary": "Phase 5 system health",
                    "description": "Get overall health status of the Phase 5 personalization system.",
                    "responses": {
                        "200": {
                            "description": "System health status",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HealthStatus"}
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/UnauthorizedError"},
                        "429": {"$ref": "#/components/responses/RateLimitError"}
                    }
                }
            }
        },
        "tags": [
            {
                "name": "Profile Management",
                "description": "User preferences and personalization features"
            },
            {
                "name": "Event Ingestion", 
                "description": "User interaction tracking and pipeline health"
            },
            {
                "name": "Analytics",
                "description": "KPIs, metrics, and system health monitoring"
            }
        ]
    }
    
    # Add schemas for all the models
    openapi_schema["components"]["schemas"] = {
        "UserPreferences": UserPreferences.schema(),
        "UserFeatures": UserFeatures.schema(),
        "UserProfile": UserProfile.schema(),
        "Event": Event.schema(),
        "SingleEventRequest": SingleEventRequest.schema(),
        "BatchEventRequest": BatchEventRequest.schema(),
        "EventResponse": EventResponse.schema(),
        "BatchEventResponse": BatchEventResponse.schema(),
        "PersonalizationKPIs": PersonalizationKPIs.schema(),
        "EngagementKPIs": EngagementKPIs.schema(),
        "ExperimentKPIs": ExperimentKPIs.schema(),
        "OverallKPIs": OverallKPIs.schema(),
        "HealthStatus": HealthStatus.schema(),
        "DataDeletionRequest": DataDeletionRequest.schema(),
        "DataDeletionResponse": DataDeletionResponse.schema()
    }
    
    return openapi_schema


# Usage examples
EXAMPLE_REQUESTS = {
    "get_user_preferences": """
# Get user preferences and features
curl -X GET "https://api.what2wear.com/v1/profile/preferences" \\
  -H "Authorization: Bearer user:your_user_id" \\
  -H "Accept: application/json"
    """,
    
    "update_preferences": """
# Update user preferences
curl -X POST "https://api.what2wear.com/v1/profile/preferences" \\
  -H "Authorization: Bearer user:your_user_id" \\
  -H "Content-Type: application/json" \\
  -d '{
    "avoid_hues": ["green", "purple"],
    "prefer_neutrals": true,
    "saturation_comfort": "medium",
    "lightness_comfort": "light", 
    "season_bias": "spring_summer"
  }'
    """,
    
    "ingest_single_event": """
# Ingest a single interaction event
curl -X POST "https://api.what2wear.com/v1/events/single" \\
  -H "Content-Type: application/json" \\
  -d '{
    "user_id": "user_123456",
    "event": {
      "event_type": "like",
      "suggestion_id": "sugg_garment_123_456",
      "colors": ["red", "white"],
      "context": {"source": "outfit_suggestions", "position": 1}
    },
    "metadata": {
      "session_id": "sess_789",
      "platform": "web"
    }
  }'
    """,
    
    "get_kpis": """
# Get 7-day KPIs
curl -X GET "https://api.what2wear.com/v1/analytics/kpis?days=7" \\
  -H "Authorization: Bearer admin:your_admin_token" \\
  -H "Accept: application/json"
    """,
    
    "delete_user_data": """
# Delete all user data (GDPR compliance)
curl -X POST "https://api.what2wear.com/v1/profile/delete" \\
  -H "Authorization: Bearer user:your_user_id" \\
  -H "Content-Type: application/json" \\
  -d '{
    "user_id": "user_123456",
    "confirmation": "DELETE_MY_DATA"
  }'
    """
}


if __name__ == "__main__":
    # Generate and save OpenAPI spec
    import json
    
    spec = get_phase5_openapi()
    
    with open("phase5_openapi.json", "w") as f:
        json.dump(spec, f, indent=2, default=str)
    
    print("OpenAPI specification generated: phase5_openapi.json")
    print("\nExample requests:")
    for name, example in EXAMPLE_REQUESTS.items():
        print(f"\n### {name}")
        print(example)
