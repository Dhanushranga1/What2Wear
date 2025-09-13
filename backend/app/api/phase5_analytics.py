"""
Phase 5 Observability Extensions.
Adds KPIs and metrics for personalization, experiments, and user engagement.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


class PersonalizationKPIs(BaseModel):
    """Key performance indicators for personalization system."""
    period_days: int
    total_sessions: int
    personalized_sessions: int
    personalization_rate: float
    avg_reranking_time_ms: float
    cache_hit_rate: float
    feature_computation_health: float


class UserEngagementMetrics(BaseModel):
    """User engagement and feedback metrics."""
    period_days: int
    total_events: int
    unique_active_users: int
    avg_events_per_user: float
    event_breakdown: Dict[str, int]
    like_rate: float
    dislike_rate: float
    apply_rate: float


class ExperimentMetrics(BaseModel):
    """A/B experiment performance metrics."""
    experiment_id: str
    status: str
    total_users: int
    variant_distribution: Dict[str, int]
    exposure_rate: float
    avg_exposures_per_user: float
    start_date: datetime
    end_date: datetime


class OverallKPIs(BaseModel):
    """Overall system KPIs for Phase 5."""
    timestamp: datetime
    period_days: int
    personalization: PersonalizationKPIs
    engagement: UserEngagementMetrics
    experiments: List[ExperimentMetrics]
    feature_health: Dict[str, float]


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


@router.get("/kpis", response_model=OverallKPIs)
async def get_overall_kpis(days: int = Query(7, ge=1, le=90, description="Analysis period in days")):
    """Get overall Phase 5 KPIs and metrics."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Personalization KPIs
                personalization_kpis = await _get_personalization_kpis(cur, days)
                
                # User engagement metrics
                engagement_metrics = await _get_engagement_metrics(cur, days)
                
                # Experiment metrics
                experiment_metrics = await _get_experiment_metrics(cur, days)
                
                # Feature health
                feature_health = await _get_feature_health(cur, days)
                
                return OverallKPIs(
                    timestamp=datetime.utcnow(),
                    period_days=days,
                    personalization=personalization_kpis,
                    engagement=engagement_metrics,
                    experiments=experiment_metrics,
                    feature_health=feature_health
                )
    
    except Exception as e:
        logger.error(f"Error getting KPIs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get KPIs")


async def _get_personalization_kpis(cur, days: int) -> PersonalizationKPIs:
    """Get personalization-specific KPIs."""
    
    # Total sessions in period
    cur.execute("""
        SELECT COUNT(*) as total_sessions,
               COUNT(CASE WHEN personalized THEN 1 END) as personalized_sessions,
               AVG(reranking_time_ms) as avg_reranking_time_ms
        FROM advice_sessions
        WHERE created_at > NOW() - INTERVAL '%s days'
    """, (days,))
    
    session_stats = cur.fetchone()
    total_sessions = session_stats['total_sessions'] or 0
    personalized_sessions = session_stats['personalized_sessions'] or 0
    avg_reranking_time = session_stats['avg_reranking_time_ms'] or 0.0
    
    personalization_rate = (personalized_sessions / total_sessions * 100) if total_sessions > 0 else 0.0
    
    # Cache hit rate (simplified - would need Redis integration for real metrics)
    cache_hit_rate = 85.0  # Placeholder - implement actual cache metrics
    
    # Feature computation health (% of users with recent feature updates)
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) as users_with_recent_features
        FROM features
        WHERE updated_at > NOW() - INTERVAL '24 hours'
    """)
    recent_features = cur.fetchone()['users_with_recent_features'] or 0
    
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) as total_active_users
        FROM events
        WHERE timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '%s days') * 1000
    """, (days,))
    total_active = cur.fetchone()['total_active_users'] or 1
    
    feature_computation_health = (recent_features / total_active * 100) if total_active > 0 else 0.0
    
    return PersonalizationKPIs(
        period_days=days,
        total_sessions=total_sessions,
        personalized_sessions=personalized_sessions,
        personalization_rate=round(personalization_rate, 2),
        avg_reranking_time_ms=round(avg_reranking_time, 2),
        cache_hit_rate=round(cache_hit_rate, 2),
        feature_computation_health=round(feature_computation_health, 2)
    )


async def _get_engagement_metrics(cur, days: int) -> UserEngagementMetrics:
    """Get user engagement metrics."""
    
    # Total events and unique users
    cur.execute("""
        SELECT COUNT(*) as total_events,
               COUNT(DISTINCT user_id) as unique_users
        FROM events
        WHERE timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '%s days') * 1000
    """, (days,))
    
    event_stats = cur.fetchone()
    total_events = event_stats['total_events'] or 0
    unique_users = event_stats['unique_users'] or 1
    
    avg_events_per_user = total_events / unique_users if unique_users > 0 else 0.0
    
    # Event breakdown by type
    cur.execute("""
        SELECT event_type, COUNT(*) as count
        FROM events
        WHERE timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '%s days') * 1000
        GROUP BY event_type
    """, (days,))
    
    event_breakdown = {row['event_type']: row['count'] for row in cur.fetchall()}
    
    # Calculate engagement rates
    total_feedback_events = event_breakdown.get('like', 0) + event_breakdown.get('dislike', 0)
    like_rate = (event_breakdown.get('like', 0) / total_feedback_events * 100) if total_feedback_events > 0 else 0.0
    dislike_rate = (event_breakdown.get('dislike', 0) / total_feedback_events * 100) if total_feedback_events > 0 else 0.0
    apply_rate = (event_breakdown.get('apply', 0) / total_events * 100) if total_events > 0 else 0.0
    
    return UserEngagementMetrics(
        period_days=days,
        total_events=total_events,
        unique_active_users=unique_users,
        avg_events_per_user=round(avg_events_per_user, 2),
        event_breakdown=event_breakdown,
        like_rate=round(like_rate, 2),
        dislike_rate=round(dislike_rate, 2),
        apply_rate=round(apply_rate, 2)
    )


async def _get_experiment_metrics(cur, days: int) -> List[ExperimentMetrics]:
    """Get A/B experiment metrics."""
    
    # Get active and recent experiments
    cur.execute("""
        SELECT experiment_id, name, status, start_date, end_date, variants
        FROM experiments
        WHERE status IN ('active', 'completed')
        AND start_date > NOW() - INTERVAL '%s days'
        ORDER BY start_date DESC
    """, (days,))
    
    experiments = cur.fetchall()
    experiment_metrics = []
    
    for exp in experiments:
        experiment_id = exp['experiment_id']
        
        # Get assignment stats
        cur.execute("""
            SELECT variant, COUNT(*) as assignment_count,
                   SUM(exposure_count) as total_exposures,
                   COUNT(CASE WHEN last_exposed_at IS NOT NULL THEN 1 END) as exposed_users
            FROM assignments
            WHERE experiment_id = %s
            GROUP BY variant
        """, (experiment_id,))
        
        variant_stats = cur.fetchall()
        
        total_users = sum(stat['assignment_count'] for stat in variant_stats)
        total_exposures = sum(stat['total_exposures'] for stat in variant_stats)
        total_exposed = sum(stat['exposed_users'] for stat in variant_stats)
        
        variant_distribution = {stat['variant']: stat['assignment_count'] for stat in variant_stats}
        exposure_rate = (total_exposed / total_users * 100) if total_users > 0 else 0.0
        avg_exposures_per_user = total_exposures / total_users if total_users > 0 else 0.0
        
        experiment_metrics.append(ExperimentMetrics(
            experiment_id=experiment_id,
            status=exp['status'],
            total_users=total_users,
            variant_distribution=variant_distribution,
            exposure_rate=round(exposure_rate, 2),
            avg_exposures_per_user=round(avg_exposures_per_user, 2),
            start_date=exp['start_date'],
            end_date=exp['end_date']
        ))
    
    return experiment_metrics


async def _get_feature_health(cur, days: int) -> Dict[str, float]:
    """Get feature computation health metrics."""
    
    # Feature update recency
    cur.execute("""
        SELECT 
            COUNT(CASE WHEN updated_at > NOW() - INTERVAL '1 hour' THEN 1 END) as updated_1h,
            COUNT(CASE WHEN updated_at > NOW() - INTERVAL '24 hours' THEN 1 END) as updated_24h,
            COUNT(CASE WHEN updated_at > NOW() - INTERVAL '7 days' THEN 1 END) as updated_7d,
            COUNT(*) as total_features
        FROM features
    """)
    
    feature_stats = cur.fetchone()
    total_features = feature_stats['total_features'] or 1
    
    health_metrics = {
        'features_updated_1h_percent': round(feature_stats['updated_1h'] / total_features * 100, 2),
        'features_updated_24h_percent': round(feature_stats['updated_24h'] / total_features * 100, 2),
        'features_updated_7d_percent': round(feature_stats['updated_7d'] / total_features * 100, 2),
        'total_users_with_features': total_features
    }
    
    # Event processing health
    cur.execute("""
        SELECT COUNT(*) as recent_events
        FROM events
        WHERE timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000
    """)
    
    recent_events = cur.fetchone()['recent_events'] or 0
    health_metrics['events_last_hour'] = recent_events
    health_metrics['event_processing_health'] = min(100.0, recent_events / 10.0 * 100)  # Expect at least 10 events/hour
    
    return health_metrics


@router.get("/personalization/performance")
async def get_personalization_performance(days: int = Query(7, ge=1, le=30)):
    """Get detailed personalization performance metrics."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Re-ranking performance over time
                cur.execute("""
                    SELECT DATE(created_at) as date,
                           COUNT(*) as total_sessions,
                           COUNT(CASE WHEN personalized THEN 1 END) as personalized_sessions,
                           AVG(reranking_time_ms) as avg_reranking_time,
                           AVG(suggestion_count) as avg_suggestions
                    FROM advice_sessions
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """, (days,))
                
                daily_stats = [dict(row) for row in cur.fetchall()]
                
                # Experiment impact on performance
                cur.execute("""
                    SELECT experiment_variant,
                           COUNT(*) as sessions,
                           AVG(reranking_time_ms) as avg_reranking_time,
                           AVG(suggestion_count) as avg_suggestions
                    FROM advice_sessions
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    AND experiment_variant IS NOT NULL
                    GROUP BY experiment_variant
                """, (days,))
                
                experiment_impact = [dict(row) for row in cur.fetchall()]
                
                return {
                    "period_days": days,
                    "daily_performance": daily_stats,
                    "experiment_impact": experiment_impact,
                    "timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Error getting personalization performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.get("/experiments/{experiment_id}/analysis")
async def get_experiment_analysis(experiment_id: str):
    """Get detailed analysis for a specific experiment."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Experiment configuration
                cur.execute("""
                    SELECT * FROM experiments WHERE experiment_id = %s
                """, (experiment_id,))
                
                experiment = cur.fetchone()
                if not experiment:
                    raise HTTPException(status_code=404, detail="Experiment not found")
                
                # Assignment and exposure statistics
                cur.execute("""
                    SELECT variant,
                           COUNT(*) as assignments,
                           SUM(exposure_count) as total_exposures,
                           AVG(exposure_count) as avg_exposures,
                           COUNT(CASE WHEN last_exposed_at IS NOT NULL THEN 1 END) as exposed_users
                    FROM assignments
                    WHERE experiment_id = %s
                    GROUP BY variant
                    ORDER BY variant
                """, (experiment_id,))
                
                variant_stats = [dict(row) for row in cur.fetchall()]
                
                # Performance by variant (if personalization experiment)
                if 'personalization' in experiment_id:
                    cur.execute("""
                        SELECT experiment_variant as variant,
                               COUNT(*) as sessions,
                               AVG(reranking_time_ms) as avg_reranking_time,
                               AVG(suggestion_count) as avg_suggestions
                        FROM advice_sessions
                        WHERE experiment_variant = ANY(%s)
                        GROUP BY experiment_variant
                    """, ([stat['variant'] for stat in variant_stats],))
                    
                    performance_stats = [dict(row) for row in cur.fetchall()]
                else:
                    performance_stats = []
                
                return {
                    "experiment": dict(experiment),
                    "variant_statistics": variant_stats,
                    "performance_by_variant": performance_stats,
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }
    
    except Exception as e:
        logger.error(f"Error getting experiment analysis for {experiment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get experiment analysis")


@router.get("/health/phase5")
async def get_phase5_health():
    """Get Phase 5 system health status."""
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Check recent activity
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM events WHERE timestamp_ms > EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000) as events_last_hour,
                        (SELECT COUNT(*) FROM advice_sessions WHERE created_at > NOW() - INTERVAL '1 hour') as sessions_last_hour,
                        (SELECT COUNT(*) FROM features WHERE updated_at > NOW() - INTERVAL '24 hours') as features_updated_24h,
                        (SELECT COUNT(*) FROM experiments WHERE status = 'active') as active_experiments
                """)
                
                health_stats = cur.fetchone()
                
                # Determine health status
                status = "healthy"
                issues = []
                
                if health_stats['events_last_hour'] == 0:
                    issues.append("No events in last hour")
                    status = "warning"
                
                if health_stats['sessions_last_hour'] == 0:
                    issues.append("No sessions in last hour")
                    status = "warning"
                
                if health_stats['features_updated_24h'] == 0:
                    issues.append("No feature updates in 24 hours")
                    status = "warning"
                
                return {
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    "component_health": {
                        "event_pipeline": "healthy" if health_stats['events_last_hour'] > 0 else "warning",
                        "personalization": "healthy" if health_stats['sessions_last_hour'] > 0 else "warning",
                        "feature_computation": "healthy" if health_stats['features_updated_24h'] > 0 else "warning",
                        "experiments": "healthy" if health_stats['active_experiments'] > 0 else "inactive"
                    },
                    "statistics": dict(health_stats),
                    "issues": issues
                }
    
    except Exception as e:
        logger.error(f"Error getting Phase 5 health: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
