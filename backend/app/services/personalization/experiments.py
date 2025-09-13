"""
Phase 5 Experimentation Framework.
Handles A/B experiment assignment, tracking, and variant management.
"""

import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for an A/B experiment."""
    experiment_id: str
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    status: str  # 'active', 'paused', 'completed'
    variants: Dict[str, float]  # variant_name -> allocation_percentage
    targeting_rules: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class UserAssignment:
    """User's assignment to an experiment variant."""
    user_id: str
    experiment_id: str
    variant: str
    assigned_at: datetime
    exposure_count: int
    last_exposed_at: Optional[datetime]


class ExperimentManager:
    """Manages A/B experiments and user assignments."""
    
    def __init__(self, db_connection_string: str):
        self.db_url = db_connection_string
        self._cache = {}  # Simple in-memory cache for experiment configs
        self._cache_ttl = 300  # 5 minutes TTL
        self._last_cache_update = 0
    
    def get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_url)
    
    def get_active_experiments(self) -> List[ExperimentConfig]:
        """Get all active experiments."""
        
        current_time = time.time()
        if current_time - self._last_cache_update > self._cache_ttl:
            self._refresh_experiment_cache()
        
        return [exp for exp in self._cache.values() if exp.status == 'active']
    
    def _refresh_experiment_cache(self):
        """Refresh experiment configuration cache."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT experiment_id, name, description, start_date, end_date,
                               status, variants, targeting_rules, metadata
                        FROM experiments
                        WHERE status IN ('active', 'paused')
                        ORDER BY start_date DESC
                    """)
                    
                    experiments = {}
                    for row in cur.fetchall():
                        exp = ExperimentConfig(
                            experiment_id=row['experiment_id'],
                            name=row['name'],
                            description=row['description'],
                            start_date=row['start_date'],
                            end_date=row['end_date'],
                            status=row['status'],
                            variants=row['variants'],
                            targeting_rules=row['targeting_rules'] or {},
                            metadata=row['metadata'] or {}
                        )
                        experiments[exp.experiment_id] = exp
                    
                    self._cache = experiments
                    self._last_cache_update = time.time()
                    
                    logger.info(f"Refreshed {len(experiments)} experiment configurations")
        
        except Exception as e:
            logger.error(f"Error refreshing experiment cache: {e}")
    
    def assign_user_to_experiments(self, user_id: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """Assign user to all applicable experiments and return variant assignments."""
        
        assignments = {}
        context = context or {}
        
        try:
            active_experiments = self.get_active_experiments()
            
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    for experiment in active_experiments:
                        # Check if user is already assigned
                        cur.execute("""
                            SELECT variant FROM assignments 
                            WHERE user_id = %s AND experiment_id = %s
                        """, (user_id, experiment.experiment_id))
                        
                        existing = cur.fetchone()
                        if existing:
                            assignments[experiment.experiment_id] = existing['variant']
                            continue
                        
                        # Check targeting rules
                        if not self._user_matches_targeting(user_id, experiment.targeting_rules, context):
                            continue
                        
                        # Assign user to variant
                        variant = self._deterministic_assignment(user_id, experiment.experiment_id, experiment.variants)
                        
                        # Store assignment
                        cur.execute("""
                            INSERT INTO assignments (user_id, experiment_id, variant, assigned_at)
                            VALUES (%s, %s, %s, NOW())
                            ON CONFLICT (user_id, experiment_id) DO NOTHING
                        """, (user_id, experiment.experiment_id, variant))
                        
                        assignments[experiment.experiment_id] = variant
                    
                    conn.commit()
        
        except Exception as e:
            logger.error(f"Error assigning user {user_id} to experiments: {e}")
        
        return assignments
    
    def _deterministic_assignment(self, user_id: str, experiment_id: str, variants: Dict[str, float]) -> str:
        """Deterministically assign user to variant based on user_id and experiment_id."""
        
        # Create deterministic hash from user_id and experiment_id
        hash_input = f"{user_id}:{experiment_id}".encode('utf-8')
        hash_value = hashlib.md5(hash_input).hexdigest()
        
        # Convert first 8 characters to integer and normalize to [0, 1)
        hash_int = int(hash_value[:8], 16)
        normalized_hash = (hash_int % 1000000) / 1000000.0
        
        # Assign to variant based on cumulative allocation
        cumulative_allocation = 0.0
        for variant, allocation in variants.items():
            cumulative_allocation += allocation / 100.0  # Convert percentage to fraction
            if normalized_hash < cumulative_allocation:
                return variant
        
        # Fallback to control group if something goes wrong
        return 'control'
    
    def _user_matches_targeting(self, user_id: str, targeting_rules: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check if user matches experiment targeting rules."""
        
        if not targeting_rules:
            return True  # No targeting rules = include all users
        
        try:
            # Check user percentage rollout
            if 'user_percentage' in targeting_rules:
                percentage = targeting_rules['user_percentage']
                hash_input = f"targeting:{user_id}".encode('utf-8')
                hash_value = hashlib.md5(hash_input).hexdigest()
                user_hash = (int(hash_value[:8], 16) % 100)
                if user_hash >= percentage:
                    return False
            
            # Check user attributes
            if 'user_attributes' in targeting_rules:
                attributes = targeting_rules['user_attributes']
                
                # Check if user is new (less than 7 days old)
                if 'new_users_only' in attributes and attributes['new_users_only']:
                    user_age_days = context.get('user_age_days', 0)
                    if user_age_days > 7:
                        return False
                
                # Check user segment
                if 'segments' in attributes:
                    user_segment = context.get('user_segment', 'default')
                    if user_segment not in attributes['segments']:
                        return False
            
            # Check time-based rules
            if 'time_rules' in targeting_rules:
                time_rules = targeting_rules['time_rules']
                current_hour = datetime.utcnow().hour
                
                if 'active_hours' in time_rules:
                    active_hours = time_rules['active_hours']
                    if current_hour not in active_hours:
                        return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error checking targeting rules for user {user_id}: {e}")
            return False  # Conservative: exclude on error
    
    def track_exposure(self, user_id: str, experiment_id: str, variant: str):
        """Track user exposure to experiment variant."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE assignments 
                        SET exposure_count = exposure_count + 1, last_exposed_at = NOW()
                        WHERE user_id = %s AND experiment_id = %s AND variant = %s
                    """, (user_id, experiment_id, variant))
                    
                    if cur.rowcount == 0:
                        # Assignment doesn't exist, create it
                        cur.execute("""
                            INSERT INTO assignments (user_id, experiment_id, variant, assigned_at, exposure_count, last_exposed_at)
                            VALUES (%s, %s, %s, NOW(), 1, NOW())
                            ON CONFLICT (user_id, experiment_id) DO UPDATE SET
                                exposure_count = assignments.exposure_count + 1,
                                last_exposed_at = NOW()
                        """, (user_id, experiment_id, variant))
                    
                    conn.commit()
        
        except Exception as e:
            logger.error(f"Error tracking exposure for user {user_id}, experiment {experiment_id}: {e}")
    
    def get_user_assignments(self, user_id: str) -> List[UserAssignment]:
        """Get all experiment assignments for a user."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT user_id, experiment_id, variant, assigned_at, exposure_count, last_exposed_at
                        FROM assignments
                        WHERE user_id = %s
                        ORDER BY assigned_at DESC
                    """, (user_id,))
                    
                    assignments = []
                    for row in cur.fetchall():
                        assignment = UserAssignment(
                            user_id=row['user_id'],
                            experiment_id=row['experiment_id'],
                            variant=row['variant'],
                            assigned_at=row['assigned_at'],
                            exposure_count=row['exposure_count'],
                            last_exposed_at=row['last_exposed_at']
                        )
                        assignments.append(assignment)
                    
                    return assignments
        
        except Exception as e:
            logger.error(f"Error getting assignments for user {user_id}: {e}")
            return []
    
    def create_experiment(self, config: ExperimentConfig) -> bool:
        """Create a new experiment."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO experiments (
                            experiment_id, name, description, start_date, end_date,
                            status, variants, targeting_rules, metadata, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        config.experiment_id,
                        config.name,
                        config.description,
                        config.start_date,
                        config.end_date,
                        config.status,
                        json.dumps(config.variants),
                        json.dumps(config.targeting_rules),
                        json.dumps(config.metadata)
                    ))
                    conn.commit()
                    
                    # Invalidate cache
                    self._last_cache_update = 0
                    
                    logger.info(f"Created experiment {config.experiment_id}")
                    return True
        
        except Exception as e:
            logger.error(f"Error creating experiment {config.experiment_id}: {e}")
            return False
    
    def update_experiment_status(self, experiment_id: str, status: str) -> bool:
        """Update experiment status."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE experiments 
                        SET status = %s, updated_at = NOW()
                        WHERE experiment_id = %s
                    """, (status, experiment_id))
                    
                    success = cur.rowcount > 0
                    conn.commit()
                    
                    if success:
                        # Invalidate cache
                        self._last_cache_update = 0
                        logger.info(f"Updated experiment {experiment_id} status to {status}")
                    
                    return success
        
        except Exception as e:
            logger.error(f"Error updating experiment {experiment_id} status: {e}")
            return False
    
    def get_experiment_stats(self, experiment_id: str) -> Dict[str, Any]:
        """Get experiment statistics."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get assignment counts by variant
                    cur.execute("""
                        SELECT variant, COUNT(*) as assignment_count,
                               SUM(exposure_count) as total_exposures,
                               COUNT(CASE WHEN last_exposed_at IS NOT NULL THEN 1 END) as exposed_users
                        FROM assignments
                        WHERE experiment_id = %s
                        GROUP BY variant
                        ORDER BY variant
                    """, (experiment_id,))
                    
                    variant_stats = {}
                    for row in cur.fetchall():
                        variant_stats[row['variant']] = {
                            'assignments': row['assignment_count'],
                            'exposures': row['total_exposures'],
                            'exposed_users': row['exposed_users']
                        }
                    
                    # Get total assignments
                    cur.execute("""
                        SELECT COUNT(*) as total_assignments
                        FROM assignments
                        WHERE experiment_id = %s
                    """, (experiment_id,))
                    
                    total_assignments = cur.fetchone()['total_assignments']
                    
                    return {
                        'experiment_id': experiment_id,
                        'total_assignments': total_assignments,
                        'variant_stats': variant_stats,
                        'generated_at': datetime.utcnow().isoformat()
                    }
        
        except Exception as e:
            logger.error(f"Error getting stats for experiment {experiment_id}: {e}")
            return {}
    
    def cleanup_expired_experiments(self) -> int:
        """Clean up assignments for expired experiments."""
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Mark expired experiments as completed
                    cur.execute("""
                        UPDATE experiments 
                        SET status = 'completed', updated_at = NOW()
                        WHERE end_date < NOW() AND status = 'active'
                    """)
                    
                    expired_count = cur.rowcount
                    conn.commit()
                    
                    if expired_count > 0:
                        # Invalidate cache
                        self._last_cache_update = 0
                        logger.info(f"Marked {expired_count} experiments as completed")
                    
                    return expired_count
        
        except Exception as e:
            logger.error(f"Error cleaning up expired experiments: {e}")
            return 0


# Factory function for dependency injection
def get_experiment_manager() -> ExperimentManager:
    """Get experiment manager instance."""
    import os
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not configured")
    
    return ExperimentManager(db_url)
