"""
Input validation service for Phase 5 API security.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ValidationError
import html
import bleach

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of input validation."""
    
    def __init__(self, is_valid: bool, sanitized_data: Any = None, errors: List[str] = None):
        self.is_valid = is_valid
        self.sanitized_data = sanitized_data
        self.errors = errors or []


class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    def __init__(self):
        # Dangerous patterns to detect
        self._sql_injection_patterns = [
            r"(\bunion\b.*\bselect\b)",
            r"(\bselect\b.*\bfrom\b)",
            r"(\bdrop\b.*\btable\b)",
            r"(\binsert\b.*\binto\b)",
            r"(\bupdate\b.*\bset\b)",
            r"(\bdelete\b.*\bfrom\b)",
            r"(\bexec\b|\bexecute\b)",
            r"(--|\#|/\*|\*/)",
            r"(\bor\b.*=.*\bor\b)",
            r"(\band\b.*=.*\band\b)"
        ]
        
        self._xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*="
        ]
        
        # Allowed HTML tags for rich content (very restrictive)
        self._allowed_html_tags = ['b', 'i', 'em', 'strong', 'span']
        self._allowed_html_attributes = {}
    
    def validate_user_id(self, user_id: str) -> ValidationResult:
        """Validate user ID format."""
        if not user_id:
            return ValidationResult(False, None, ["User ID is required"])
        
        # User ID should be alphanumeric with hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9_-]{3,64}$', user_id):
            return ValidationResult(False, None, ["Invalid user ID format"])
        
        return ValidationResult(True, user_id.strip())
    
    def validate_color_hex(self, color_hex: str) -> ValidationResult:
        """Validate hex color format."""
        if not color_hex:
            return ValidationResult(False, None, ["Color hex is required"])
        
        # Ensure it starts with # and has 6 hex digits
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color_hex):
            return ValidationResult(False, None, ["Invalid hex color format"])
        
        return ValidationResult(True, color_hex.upper())
    
    def validate_color_list(self, colors: List[str]) -> ValidationResult:
        """Validate a list of color names."""
        if not isinstance(colors, list):
            return ValidationResult(False, None, ["Colors must be a list"])
        
        if len(colors) > 20:
            return ValidationResult(False, None, ["Too many colors (max 20)"])
        
        sanitized_colors = []
        errors = []
        
        for color in colors:
            if not isinstance(color, str):
                errors.append(f"Invalid color type: {type(color)}")
                continue
            
            # Sanitize color name
            sanitized_color = self._sanitize_text(color, max_length=50)
            if sanitized_color:
                sanitized_colors.append(sanitized_color)
        
        if errors:
            return ValidationResult(False, None, errors)
        
        return ValidationResult(True, sanitized_colors)
    
    def validate_event_data(self, event_data: Dict[str, Any]) -> ValidationResult:
        """Validate event data structure."""
        required_fields = ['event_type', 'user_id']
        errors = []
        
        for field in required_fields:
            if field not in event_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate event type
        valid_event_types = ['like', 'dislike', 'view', 'apply', 'skip', 'preference_update', 'session_start', 'session_end']
        if 'event_type' in event_data and event_data['event_type'] not in valid_event_types:
            errors.append(f"Invalid event type: {event_data['event_type']}")
        
        # Validate user_id
        if 'user_id' in event_data:
            user_validation = self.validate_user_id(event_data['user_id'])
            if not user_validation.is_valid:
                errors.extend(user_validation.errors)
        
        # Sanitize additional data
        sanitized_data = {}
        for key, value in event_data.items():
            if isinstance(value, str):
                sanitized_data[key] = self._sanitize_text(value, max_length=1000)
            elif isinstance(value, (int, float, bool)):
                sanitized_data[key] = value
            elif isinstance(value, list):
                if key == 'colors':
                    color_validation = self.validate_color_list(value)
                    if color_validation.is_valid:
                        sanitized_data[key] = color_validation.sanitized_data
                    else:
                        errors.extend(color_validation.errors)
                else:
                    # Sanitize string lists
                    sanitized_list = []
                    for item in value[:20]:  # Limit list size
                        if isinstance(item, str):
                            sanitized_list.append(self._sanitize_text(item, max_length=100))
                    sanitized_data[key] = sanitized_list
            elif isinstance(value, dict):
                # Recursively validate nested objects (limited depth)
                if len(str(value)) < 5000:  # Prevent huge payloads
                    sanitized_data[key] = self._sanitize_dict(value, max_depth=3)
                else:
                    errors.append(f"Field {key} is too large")
        
        if errors:
            return ValidationResult(False, None, errors)
        
        return ValidationResult(True, sanitized_data)
    
    def validate_preference_data(self, pref_data: Dict[str, Any]) -> ValidationResult:
        """Validate user preference data."""
        errors = []
        sanitized_data = {}
        
        # Validate avoid_hues
        if 'avoid_hues' in pref_data:
            if isinstance(pref_data['avoid_hues'], list):
                color_validation = self.validate_color_list(pref_data['avoid_hues'])
                if color_validation.is_valid:
                    sanitized_data['avoid_hues'] = color_validation.sanitized_data
                else:
                    errors.extend(color_validation.errors)
            else:
                errors.append("avoid_hues must be a list")
        
        # Validate boolean preferences
        bool_fields = ['prefer_neutrals']
        for field in bool_fields:
            if field in pref_data:
                if isinstance(pref_data[field], bool):
                    sanitized_data[field] = pref_data[field]
                else:
                    errors.append(f"{field} must be a boolean")
        
        # Validate enum preferences
        enum_validations = {
            'saturation_comfort': ['low', 'medium', 'high'],
            'lightness_comfort': ['dark', 'mid', 'light'],
            'season_bias': ['all', 'spring_summer', 'autumn_winter']
        }
        
        for field, valid_values in enum_validations.items():
            if field in pref_data:
                if pref_data[field] in valid_values:
                    sanitized_data[field] = pref_data[field]
                else:
                    errors.append(f"{field} must be one of: {valid_values}")
        
        if errors:
            return ValidationResult(False, None, errors)
        
        return ValidationResult(True, sanitized_data)
    
    def check_sql_injection(self, text: str) -> bool:
        """Check for SQL injection patterns."""
        text_lower = text.lower()
        
        for pattern in self._sql_injection_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return True
        
        return False
    
    def check_xss(self, text: str) -> bool:
        """Check for XSS patterns."""
        text_lower = text.lower()
        
        for pattern in self._xss_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {pattern}")
                return True
        
        return False
    
    def _sanitize_text(self, text: str, max_length: int = 1000) -> str:
        """Sanitize text input."""
        if not isinstance(text, str):
            return ""
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length]
        
        # HTML escape
        text = html.escape(text)
        
        # Remove potentially dangerous patterns
        if self.check_sql_injection(text) or self.check_xss(text):
            logger.warning(f"Dangerous pattern detected in text: {text[:100]}")
            return ""  # Reject entirely if dangerous
        
        # Clean with bleach for extra safety
        text = bleach.clean(text, tags=self._allowed_html_tags, attributes=self._allowed_html_attributes)
        
        return text.strip()
    
    def _sanitize_dict(self, data: Dict[str, Any], max_depth: int = 3) -> Dict[str, Any]:
        """Recursively sanitize dictionary data."""
        if max_depth <= 0:
            return {}
        
        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            safe_key = self._sanitize_text(str(key), max_length=100)
            if not safe_key:
                continue
            
            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[safe_key] = self._sanitize_text(value, max_length=1000)
            elif isinstance(value, (int, float, bool)):
                sanitized[safe_key] = value
            elif isinstance(value, list):
                sanitized_list = []
                for item in value[:20]:  # Limit list size
                    if isinstance(item, str):
                        sanitized_list.append(self._sanitize_text(item, max_length=100))
                    elif isinstance(item, (int, float, bool)):
                        sanitized_list.append(item)
                sanitized[safe_key] = sanitized_list
            elif isinstance(value, dict):
                sanitized[safe_key] = self._sanitize_dict(value, max_depth - 1)
        
        return sanitized


# Global validator instance
_input_validator = None


def get_input_validator() -> InputValidator:
    """Get global input validator instance."""
    global _input_validator
    
    if _input_validator is None:
        _input_validator = InputValidator()
    
    return _input_validator
