"""
Phase 5 Event Ingestion Pipeline.
Handles user interaction events for feedback-driven personalization.
"""

import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field, validator
import psycopg2
from psycopg2.extras import RealDictCursor
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/events", tags=["events"])


# Pydantic models for event data
class EventMetadata(BaseModel):
    """Event metadata for context."""
    session_id: Optional[str] = None
    user_agent: Optional[str] = None
    platform: Optional[str] = None
    experiment_id: Optional[str] = None
    ab_variant: Optional[str] = None
    additional_data: Dict[str, Any] = Field(default_factory=dict)


class SuggestionEvent(BaseModel):
    """Events related to color suggestions."""
    event_type: str = Field(..., description="like, dislike, view, apply")
    suggestion_id: str = Field(..., description="ID of the suggestion")
    colors: List[str] = Field(..., description="Colors in the suggestion")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    
    @validator('event_type')
    def validate_event_type(cls, v):
        valid_types = ['like', 'dislike', 'view', 'apply', 'skip']
        if v not in valid_types:
            raise ValueError(f'event_type must be one of: {valid_types}')
        return v


class PreferenceEvent(BaseModel):
    """Events related to preference changes."""
    event_type: str = "preference_update"
    preference_type: str = Field(..., description="Type of preference updated")
    old_value: Any = Field(..., description="Previous value")
    new_value: Any = Field(..., description="New value")
    
    @validator('preference_type')
    def validate_preference_type(cls, v):
        valid_types = ['avoid_hues', 'prefer_neutrals', 'saturation_comfort', 'lightness_comfort', 'season_bias']
        if v not in valid_types:
            raise ValueError(f'preference_type must be one of: {valid_types}')
        return v


class SessionEvent(BaseModel):
    """Events related to advice sessions."""
    event_type: str = Field(..., description="session_start, session_end, item_upload")
    session_id: str = Field(..., description="Session identifier")
    item_id: Optional[str] = None
    duration_ms: Optional[int] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('event_type')
    def validate_event_type(cls, v):
        valid_types = ['session_start', 'session_end', 'item_upload', 'item_view']
        if v not in valid_types:
            raise ValueError(f'event_type must be one of: {valid_types}')
        return v


class EventBatch(BaseModel):
    """Batch of events for efficient processing."""
    user_id: str = Field(..., description="User identifier")
    events: List[Union[SuggestionEvent, PreferenceEvent, SessionEvent]] = Field(..., min_items=1, max_items=100)
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    client_timestamp_ms: Optional[int] = None


class SingleEvent(BaseModel):
    """Single event wrapper."""
    user_id: str = Field(..., description="User identifier")
    event: Union[SuggestionEvent, PreferenceEvent, SessionEvent] = Field(..., description="Event data")
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    client_timestamp_ms: Optional[int] = None


# Database connection helper
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


# Event processing functions
async def process_event_batch(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process a batch of events and store in database."""
    
    if not events:
        return {"processed": 0, "errors": 0}
    
    processed_count = 0
    error_count = 0
    start_time = time.time()
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Batch insert events
                event_records = []
                for event_data in events:
                    try:
                        record = (
                            event_data['user_id'],
                            event_data['event_type'],
                            event_data['timestamp_ms'],
                            json.dumps(event_data['data']),
                            event_data.get('session_id'),
                            event_data.get('suggestion_id'),
                            event_data.get('item_id'),
                            event_data.get('experiment_id'),
                            json.dumps(event_data.get('metadata', {}))
                        )
                        event_records.append(record)
                    except Exception as e:
                        logger.error(f"Error preparing event record: {e}")
                        error_count += 1
                
                # Bulk insert
                if event_records:
                    cur.executemany("""
                        INSERT INTO events (
                            user_id, event_type, timestamp_ms, data, session_id,
                            suggestion_id, item_id, experiment_id, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, event_records)
                    
                    processed_count = len(event_records)
                    conn.commit()
                    
                    logger.info(f"Processed {processed_count} events in {time.time() - start_time:.3f}s")
    
    except Exception as e:
        logger.error(f"Error processing event batch: {e}")
        error_count += len(events)
    
    return {"processed": processed_count, "errors": error_count, "duration_ms": int((time.time() - start_time) * 1000)}


def normalize_event_data(event_data: Dict[str, Any], user_id: str, metadata: EventMetadata) -> Dict[str, Any]:
    """Normalize event data for database storage."""
    
    timestamp_ms = event_data.get('client_timestamp_ms') or int(time.time() * 1000)
    
    # Extract common fields
    result = {
        'user_id': user_id,
        'event_type': event_data['event']['event_type'],
        'timestamp_ms': timestamp_ms,
        'data': event_data['event'].dict(),
        'metadata': metadata.dict()
    }
    
    # Add optional fields based on event type
    event = event_data['event']
    if hasattr(event, 'session_id') and event.session_id:
        result['session_id'] = event.session_id
    elif metadata.session_id:
        result['session_id'] = metadata.session_id
    
    if hasattr(event, 'suggestion_id') and event.suggestion_id:
        result['suggestion_id'] = event.suggestion_id
    
    if hasattr(event, 'item_id') and event.item_id:
        result['item_id'] = event.item_id
    
    if metadata.experiment_id:
        result['experiment_id'] = metadata.experiment_id
    
    return result


# API endpoints
@router.post("/batch")
async def ingest_event_batch(batch: EventBatch, background_tasks: BackgroundTasks):
    """Ingest a batch of events for processing."""
    
    try:
        # Normalize events for processing
        normalized_events = []
        for event in batch.events:
            event_data = {
                'event': event,
                'client_timestamp_ms': batch.client_timestamp_ms
            }
            normalized = normalize_event_data(event_data, batch.user_id, batch.metadata)
            normalized_events.append(normalized)
        
        # Process events in background
        background_tasks.add_task(process_event_batch, normalized_events)
        
        return {
            "status": "accepted",
            "batch_id": f"{batch.user_id}_{int(time.time() * 1000)}",
            "event_count": len(batch.events),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error ingesting event batch: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest events")


@router.post("/single")
async def ingest_single_event(event_data: SingleEvent, background_tasks: BackgroundTasks):
    """Ingest a single event."""
    
    try:
        # Convert to batch format for processing
        normalized = normalize_event_data(event_data.dict(), event_data.user_id, event_data.metadata)
        
        # Process in background
        background_tasks.add_task(process_event_batch, [normalized])
        
        return {
            "status": "accepted",
            "event_id": f"{event_data.user_id}_{int(time.time() * 1000)}",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error ingesting single event: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest event")


@router.get("/health")
async def event_pipeline_health():
    """Check event pipeline health."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check recent event volume
                cur.execute("""
                    SELECT COUNT(*) as count 
                    FROM events 
                    WHERE timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000
                """)
                recent_count = cur.fetchone()[0]
                
                # Check for errors or delays
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM events 
                    WHERE timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '5 minutes') * 1000
                """)
                very_recent_count = cur.fetchone()[0]
                
                return {
                    "status": "healthy",
                    "events_last_hour": recent_count,
                    "events_last_5min": very_recent_count,
                    "timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Event pipeline health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/stats/{user_id}")
async def get_user_event_stats(user_id: str, days: int = 7):
    """Get event statistics for a user."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get event counts by type
                cur.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM events 
                    WHERE user_id = %s 
                    AND timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '%s days') * 1000
                    GROUP BY event_type
                    ORDER BY count DESC
                """, (user_id, days))
                
                event_counts = {row['event_type']: row['count'] for row in cur.fetchall()}
                
                # Get total events
                total_events = sum(event_counts.values())
                
                return {
                    "user_id": user_id,
                    "period_days": days,
                    "total_events": total_events,
                    "event_counts": event_counts,
                    "timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Error getting event stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get event statistics")


@router.delete("/user/{user_id}")
async def delete_user_events(user_id: str):
    """Delete all events for a user (GDPR compliance)."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM events WHERE user_id = %s", (user_id,))
                deleted_count = cur.rowcount
                conn.commit()
                
                logger.info(f"Deleted {deleted_count} events for user {user_id}")
                
                return {
                    "status": "success",
                    "deleted_events": deleted_count,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Error deleting events for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user events")
