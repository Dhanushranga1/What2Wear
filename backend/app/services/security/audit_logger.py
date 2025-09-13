"""
Audit logging service for Phase 5 security and compliance.
"""

import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of events to audit."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PROFILE_ACCESS = "profile_access"
    PROFILE_UPDATE = "profile_update"
    DATA_DELETION = "data_deletion"
    EVENT_INGESTION = "event_ingestion"
    FEATURE_COMPUTATION = "feature_computation"
    EXPERIMENT_ASSIGNMENT = "experiment_assignment"
    PERSONALIZATION_APPLIED = "personalization_applied"
    PRIVACY_OPT_OUT = "privacy_opt_out"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    VALIDATION_FAILED = "validation_failed"
    SECURITY_INCIDENT = "security_incident"


@dataclass
class AuditEvent:
    """Audit event record."""
    event_type: AuditEventType
    user_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime
    details: Dict[str, Any]
    session_id: Optional[str] = None
    request_id: Optional[str] = None


class AuditLogger:
    """Audit logging service for security and compliance."""
    
    def __init__(self, db_connection_string: str = None):
        self.db_url = db_connection_string
        self._local_logs = []  # Fallback for when DB is unavailable
        self._max_local_logs = 1000
    
    def get_db_connection(self):
        """Get database connection."""
        if not self.db_url:
            import os
            self.db_url = os.getenv('DATABASE_URL')
        
        if self.db_url:
            return psycopg2.connect(self.db_url)
        return None
    
    def log_event(
        self,
        event_type: AuditEventType,
        user_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        details: Dict[str, Any] = None,
        session_id: str = None,
        request_id: str = None
    ):
        """Log an audit event."""
        
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow(),
            details=details or {},
            session_id=session_id,
            request_id=request_id
        )
        
        # Try to store in database first
        if self._store_in_database(event):
            return
        
        # Fallback to local storage
        self._store_locally(event)
        
        # Log critical events to application log as well
        if event_type in [AuditEventType.SECURITY_INCIDENT, AuditEventType.DATA_DELETION]:
            logger.critical(f"AUDIT: {event_type.value} - User: {user_id}, Details: {details}")
    
    def _store_in_database(self, event: AuditEvent) -> bool:
        """Store audit event in database."""
        try:
            conn = self.get_db_connection()
            if not conn:
                return False
            
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO audit_logs (
                            event_type, user_id, ip_address, user_agent,
                            timestamp, details, session_id, request_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        event.event_type.value,
                        event.user_id,
                        event.ip_address,
                        event.user_agent,
                        event.timestamp,
                        json.dumps(event.details),
                        event.session_id,
                        event.request_id
                    ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store audit event in database: {e}")
            return False
    
    def _store_locally(self, event: AuditEvent):
        """Store audit event locally as fallback."""
        
        # Convert to dict for JSON serialization
        event_dict = {
            'event_type': event.event_type.value,
            'user_id': event.user_id,
            'ip_address': event.ip_address,
            'user_agent': event.user_agent,
            'timestamp': event.timestamp.isoformat(),
            'details': event.details,
            'session_id': event.session_id,
            'request_id': event.request_id
        }
        
        self._local_logs.append(event_dict)
        
        # Limit local storage size
        if len(self._local_logs) > self._max_local_logs:
            self._local_logs = self._local_logs[-self._max_local_logs:]
        
        # Also log to file
        logger.info(f"AUDIT_EVENT: {json.dumps(event_dict)}")
    
    def get_user_audit_trail(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get audit trail for a specific user."""
        
        try:
            conn = self.get_db_connection()
            if not conn:
                # Return local logs if DB unavailable
                return [log for log in self._local_logs if log.get('user_id') == user_id]
            
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT event_type, timestamp, details, ip_address, session_id
                        FROM audit_logs
                        WHERE user_id = %s 
                        AND timestamp > NOW() - INTERVAL '%s days'
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    """, (user_id, days))
                    
                    return [dict(row) for row in cur.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get audit trail for user {user_id}: {e}")
            return []
    
    def get_security_incidents(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent security incidents."""
        
        security_events = [
            AuditEventType.SECURITY_INCIDENT,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.VALIDATION_FAILED
        ]
        
        try:
            conn = self.get_db_connection()
            if not conn:
                # Return local incidents
                return [
                    log for log in self._local_logs 
                    if log.get('event_type') in [e.value for e in security_events]
                ]
            
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT event_type, user_id, ip_address, timestamp, details
                        FROM audit_logs
                        WHERE event_type = ANY(%s)
                        AND timestamp > NOW() - INTERVAL '%s days'
                        ORDER BY timestamp DESC
                        LIMIT 500
                    """, ([e.value for e in security_events], days))
                    
                    return [dict(row) for row in cur.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get security incidents: {e}")
            return []
    
    def get_audit_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get audit statistics."""
        
        try:
            conn = self.get_db_connection()
            if not conn:
                # Return local stats
                recent_logs = [
                    log for log in self._local_logs
                    if (datetime.utcnow() - datetime.fromisoformat(log['timestamp'])).days <= days
                ]
                
                event_counts = {}
                for log in recent_logs:
                    event_type = log['event_type']
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1
                
                return {
                    'total_events': len(recent_logs),
                    'unique_users': len(set(log.get('user_id') for log in recent_logs if log.get('user_id'))),
                    'event_counts': event_counts,
                    'source': 'local_cache'
                }
            
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Total events and unique users
                    cur.execute("""
                        SELECT COUNT(*) as total_events,
                               COUNT(DISTINCT user_id) as unique_users
                        FROM audit_logs
                        WHERE timestamp > NOW() - INTERVAL '%s days'
                    """, (days,))
                    
                    stats = dict(cur.fetchone())
                    
                    # Event counts by type
                    cur.execute("""
                        SELECT event_type, COUNT(*) as count
                        FROM audit_logs
                        WHERE timestamp > NOW() - INTERVAL '%s days'
                        GROUP BY event_type
                        ORDER BY count DESC
                    """, (days,))
                    
                    event_counts = {row['event_type']: row['count'] for row in cur.fetchall()}
                    stats['event_counts'] = event_counts
                    stats['source'] = 'database'
                    
                    return stats
        
        except Exception as e:
            logger.error(f"Failed to get audit stats: {e}")
            return {'error': str(e)}
    
    def create_audit_table(self):
        """Create audit_logs table if it doesn't exist."""
        
        try:
            conn = self.get_db_connection()
            if not conn:
                logger.warning("No database connection for audit table creation")
                return False
            
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS audit_logs (
                            id BIGSERIAL PRIMARY KEY,
                            event_type VARCHAR(50) NOT NULL,
                            user_id VARCHAR(100),
                            ip_address INET,
                            user_agent TEXT,
                            timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                            details JSONB,
                            session_id VARCHAR(100),
                            request_id VARCHAR(100),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                        
                        CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
                        CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
                        CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
                        CREATE INDEX IF NOT EXISTS idx_audit_logs_session_id ON audit_logs(session_id);
                    """)
            
            logger.info("Audit logs table created/verified")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create audit table: {e}")
            return False


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    
    if _audit_logger is None:
        _audit_logger = AuditLogger()
        # Try to create table on first access
        _audit_logger.create_audit_table()
    
    return _audit_logger


# Convenience functions for common audit events
def log_user_login(user_id: str, ip_address: str = None, user_agent: str = None):
    """Log user login event."""
    get_audit_logger().log_event(
        AuditEventType.USER_LOGIN,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_profile_access(user_id: str, accessed_by: str = None, ip_address: str = None):
    """Log profile access event."""
    get_audit_logger().log_event(
        AuditEventType.PROFILE_ACCESS,
        user_id=user_id,
        ip_address=ip_address,
        details={'accessed_by': accessed_by or user_id}
    )


def log_data_deletion(user_id: str, deletion_type: str, ip_address: str = None):
    """Log data deletion event."""
    get_audit_logger().log_event(
        AuditEventType.DATA_DELETION,
        user_id=user_id,
        ip_address=ip_address,
        details={'deletion_type': deletion_type}
    )


def log_security_incident(incident_type: str, user_id: str = None, ip_address: str = None, details: Dict[str, Any] = None):
    """Log security incident."""
    get_audit_logger().log_event(
        AuditEventType.SECURITY_INCIDENT,
        user_id=user_id,
        ip_address=ip_address,
        details={'incident_type': incident_type, **(details or {})}
    )
