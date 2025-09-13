"""
StyleSync Request ID Utilities
Generate unique request IDs for tracing.
"""
import uuid
from datetime import datetime


def generate_request_id() -> str:
    """
    Generate a unique request ID for tracking.
    
    Returns:
        Unique request ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"seg-{timestamp}-{short_uuid}"


def extract_timestamp_from_request_id(request_id: str) -> str:
    """
    Extract timestamp from request ID.
    
    Args:
        request_id: Request ID string
        
    Returns:
        Timestamp string or empty if not found
    """
    try:
        parts = request_id.split("-")
        if len(parts) >= 2 and parts[0] == "seg":
            return parts[1]
    except Exception:
        pass
    return ""
