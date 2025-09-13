"""
Phase 5 User Profile Management API endpoints.
Handles user preferences, features, and data deletion.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
import psycopg2
from psycopg2.extras import RealDictCursor

from app.services.personalization import get_feature_cache, UserFeatures
from app.services.security import get_security_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/profile", tags=["profile"])
security = HTTPBearer()


# Pydantic models for API contracts
class UserPreferences(BaseModel):
    """User preference settings."""
    avoid_hues: List[str] = Field(default_factory=list, description="Hue names to avoid (e.g., ['green', 'purple'])")
    prefer_neutrals: bool = Field(default=False, description="Prefer neutral colors")
    saturation_comfort: str = Field(default="medium", description="Comfort with saturation: low, medium, high")
    lightness_comfort: str = Field(default="mid", description="Comfort with lightness: dark, mid, light")
    season_bias: str = Field(default="all", description="Season preference: all, spring_summer, autumn_winter")
    
    @validator('saturation_comfort')
    def validate_saturation_comfort(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('saturation_comfort must be low, medium, or high')
        return v
    
    @validator('lightness_comfort')
    def validate_lightness_comfort(cls, v):
        if v not in ['dark', 'mid', 'light']:
            raise ValueError('lightness_comfort must be dark, mid, or light')
        return v
    
    @validator('season_bias')
    def validate_season_bias(cls, v):
        if v not in ['all', 'spring_summer', 'autumn_winter']:
            raise ValueError('season_bias must be all, spring_summer, or autumn_winter')
        return v
    
    @validator('avoid_hues')
    def validate_avoid_hues(cls, v):
        valid_hues = ['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'brown', 'gray']
        for hue in v:
            if hue.lower() not in valid_hues:
                raise ValueError(f'Invalid hue: {hue}. Valid hues: {valid_hues}')
        return [h.lower() for h in v]


class UserProfile(BaseModel):
    """Complete user profile including preferences and derived features."""
    user_id: str
    preferences: UserPreferences
    features: Dict[str, Any]
    created_at: datetime
    last_seen_at: datetime
    opt_out_personalization: bool = False
    opt_out_experiments: bool = False


class DeleteRequest(BaseModel):
    """Request for user data deletion."""
    user_id: str
    confirmation: str = Field(..., description="Must be 'DELETE_MY_DATA' to confirm")
    
    @validator('confirmation')
    def validate_confirmation(cls, v):
        if v != 'DELETE_MY_DATA':
            raise ValueError('confirmation must be exactly "DELETE_MY_DATA"')
        return v


# Dependency injection
def get_db_connection():
    """Get database connection from environment."""
    import os
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")


def verify_user_auth(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verify user authentication and extract user_id.
    In production, this would validate JWT tokens or API keys.
    For MVP, we'll extract user_id from the token directly.
    """
    token = credentials.credentials
    
    # For MVP, simple token format: "user:{user_id}" 
    # In production, use proper JWT validation
    if not token.startswith('user:'):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    user_id = token[5:]  # Remove "user:" prefix
    if not user_id or len(user_id) < 3:
        raise HTTPException(status_code=401, detail="Invalid user ID")
    
    return user_id


# Rate limiting decorator
def rate_limit_profile(max_requests: int = 10, window_seconds: int = 60):
    """Rate limiting for profile endpoints."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user_id from kwargs
            user_id = kwargs.get('user_id') or (args[1] if len(args) > 1 else None)
            if user_id:
                # Simple in-memory rate limiting (in production, use Redis)
                # This is a simplified implementation
                pass
            return await func(*args, **kwargs)
        return wrapper
    return decorator


@router.get("/preferences", response_model=UserProfile)
async def get_user_preferences(request: Request, user_id: str = Depends(verify_user_auth)):
    """Get user preferences and derived features."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get user record
                cur.execute("""
                    SELECT user_id, created_at, last_seen_at, opt_out_personalization, opt_out_experiments
                    FROM users WHERE user_id = %s
                """, (user_id,))
                user_row = cur.fetchone()
                
                if not user_row:
                    # Create user record if it doesn't exist
                    cur.execute("""
                        INSERT INTO users (user_id, created_at, last_seen_at)
                        VALUES (%s, NOW(), NOW())
                        RETURNING user_id, created_at, last_seen_at, opt_out_personalization, opt_out_experiments
                    """, (user_id,))
                    user_row = cur.fetchone()
                    conn.commit()
                
                # Get preferences
                cur.execute("""
                    SELECT avoid_hues, prefer_neutrals, saturation_comfort, 
                           lightness_comfort, season_bias
                    FROM preferences WHERE user_id = %s
                """, (user_id,))
                pref_row = cur.fetchone()
                
                # Get features
                feature_cache = get_feature_cache()
                features = feature_cache.get_features_sync(user_id)
                
                # Build preferences object
                if pref_row:
                    preferences = UserPreferences(
                        avoid_hues=pref_row['avoid_hues'] or [],
                        prefer_neutrals=pref_row['prefer_neutrals'],
                        saturation_comfort=pref_row['saturation_comfort'],
                        lightness_comfort=pref_row['lightness_comfort'],
                        season_bias=pref_row['season_bias']
                    )
                else:
                    preferences = UserPreferences()
                
                # Build profile response
                profile = UserProfile(
                    user_id=user_row['user_id'],
                    preferences=preferences,
                    features={
                        'hue_bias': features.hue_bias,
                        'neutral_affinity': features.neutral_affinity,
                        'saturation_cap_adjust': features.saturation_cap_adjust,
                        'lightness_bias': features.lightness_bias,
                        'event_count': features.event_count,
                        'updated_at': features.updated_at.isoformat()
                    },
                    created_at=user_row['created_at'],
                    last_seen_at=user_row['last_seen_at'],
                    opt_out_personalization=user_row['opt_out_personalization'],
                    opt_out_experiments=user_row['opt_out_experiments']
                )
                
                return profile
    
    except Exception as e:
        logger.error(f"Error getting preferences for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user preferences")


@router.post("/preferences", response_model=UserProfile)
async def update_user_preferences(
    preferences: UserPreferences,
    request: Request, 
    user_id: str = Depends(verify_user_auth)
):
    """Update user preferences."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Ensure user exists
                cur.execute("""
                    INSERT INTO users (user_id, created_at, last_seen_at)
                    VALUES (%s, NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE SET last_seen_at = NOW()
                """, (user_id,))
                
                # Upsert preferences
                cur.execute("""
                    INSERT INTO preferences (
                        user_id, avoid_hues, prefer_neutrals, saturation_comfort,
                        lightness_comfort, season_bias, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        avoid_hues = EXCLUDED.avoid_hues,
                        prefer_neutrals = EXCLUDED.prefer_neutrals,
                        saturation_comfort = EXCLUDED.saturation_comfort,
                        lightness_comfort = EXCLUDED.lightness_comfort,
                        season_bias = EXCLUDED.season_bias,
                        updated_at = EXCLUDED.updated_at
                """, (
                    user_id,
                    preferences.avoid_hues,
                    preferences.prefer_neutrals,
                    preferences.saturation_comfort,
                    preferences.lightness_comfort,
                    preferences.season_bias
                ))
                
                conn.commit()
                
                # Invalidate feature cache to force refresh
                feature_cache = get_feature_cache()
                feature_cache.invalidate_cache_sync(user_id)
                
                logger.info(f"Updated preferences for user {user_id}")
    
    except Exception as e:
        logger.error(f"Error updating preferences for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")
    
    # Return updated profile
    return await get_user_preferences(request, user_id)


@router.post("/delete")
async def delete_user_data(
    delete_request: DeleteRequest,
    request: Request,
    user_id: str = Depends(verify_user_auth)
):
    """Delete all user data (GDPR compliance)."""
    
    # Verify user is deleting their own data
    if delete_request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Can only delete your own data")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Delete in order to respect foreign key constraints
                tables_to_clear = [
                    'events',
                    'suggestions', 
                    'advice_sessions',
                    'assignments',
                    'features',
                    'preferences',
                    'users'
                ]
                
                deleted_counts = {}
                for table in tables_to_clear:
                    cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
                    deleted_counts[table] = cur.rowcount
                
                conn.commit()
                
                # Invalidate cache
                feature_cache = get_feature_cache()
                feature_cache.invalidate_cache_sync(user_id)
                
                logger.info(f"Deleted all data for user {user_id}: {deleted_counts}")
                
                return {
                    "status": "success",
                    "message": f"All data for user {user_id} has been deleted",
                    "deleted_records": deleted_counts,
                    "timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Error deleting data for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user data")


@router.get("/stats")
async def get_profile_stats(request: Request, user_id: str = Depends(verify_user_auth)):
    """Get user statistics and activity summary."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get event counts by type
                cur.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM events 
                    WHERE user_id = %s AND timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days') * 1000
                    GROUP BY event_type
                    ORDER BY count DESC
                """, (user_id,))
                event_counts = {row['event_type']: row['count'] for row in cur.fetchall()}
                
                # Get total advice sessions
                cur.execute("""
                    SELECT COUNT(*) as total_sessions,
                           COUNT(CASE WHEN personalized THEN 1 END) as personalized_sessions
                    FROM advice_sessions 
                    WHERE user_id = %s AND created_at > NOW() - INTERVAL '30 days'
                """, (user_id,))
                session_stats = cur.fetchone()
                
                # Get feature cache stats
                feature_cache = get_feature_cache()
                cache_stats = feature_cache.get_cache_stats()
                
                return {
                    "user_id": user_id,
                    "period": "last_30_days",
                    "event_counts": event_counts,
                    "session_stats": dict(session_stats) if session_stats else {},
                    "cache_stats": cache_stats,
                    "timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Error getting stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user stats")


@router.post("/opt-out")
async def update_opt_out_settings(
    request: Request,
    user_id: str = Depends(verify_user_auth),
    opt_out_personalization: bool = False,
    opt_out_experiments: bool = False
):
    """Update user opt-out preferences."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET opt_out_personalization = %s, opt_out_experiments = %s, last_seen_at = NOW()
                    WHERE user_id = %s
                """, (opt_out_personalization, opt_out_experiments, user_id))
                
                if cur.rowcount == 0:
                    # User doesn't exist, create them
                    cur.execute("""
                        INSERT INTO users (user_id, opt_out_personalization, opt_out_experiments)
                        VALUES (%s, %s, %s)
                    """, (user_id, opt_out_personalization, opt_out_experiments))
                
                conn.commit()
                
                logger.info(f"Updated opt-out settings for user {user_id}: personalization={opt_out_personalization}, experiments={opt_out_experiments}")
                
                return {
                    "status": "success",
                    "user_id": user_id,
                    "opt_out_personalization": opt_out_personalization,
                    "opt_out_experiments": opt_out_experiments,
                    "timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Error updating opt-out settings for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update opt-out settings")
