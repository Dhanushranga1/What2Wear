"""
Encryption service for Phase 5 data protection.
"""

import logging
import os
import base64
import hashlib
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting sensitive data."""
    
    def __init__(self, encryption_key: str = None):
        self._fernet = None
        
        if encryption_key:
            self._init_encryption(encryption_key)
        else:
            # Try to get from environment
            env_key = os.getenv('STYLESYNC_ENCRYPTION_KEY')
            if env_key:
                self._init_encryption(env_key)
            else:
                logger.warning("No encryption key provided - encryption disabled")
    
    def _init_encryption(self, key: str):
        """Initialize Fernet encryption with the provided key."""
        try:
            # If key is a password, derive a proper key
            if len(key) != 44:  # Fernet keys are 44 chars base64 encoded
                key = self._derive_key_from_password(key)
            
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            logger.info("Encryption service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            self._fernet = None
    
    def _derive_key_from_password(self, password: str) -> str:
        """Derive a Fernet key from a password."""
        
        # Use a fixed salt for deterministic key derivation
        # In production, consider using a configurable salt
        salt = b'stylesync_salt_v1'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key.decode()
    
    def is_encryption_enabled(self) -> bool:
        """Check if encryption is enabled."""
        return self._fernet is not None
    
    def encrypt(self, data: str) -> Optional[str]:
        """Encrypt a string and return base64 encoded result."""
        
        if not self._fernet:
            logger.warning("Encryption requested but not available")
            return data  # Return unencrypted if encryption not available
        
        try:
            encrypted_bytes = self._fernet.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return None
    
    def decrypt(self, encrypted_data: str) -> Optional[str]:
        """Decrypt base64 encoded data."""
        
        if not self._fernet:
            logger.warning("Decryption requested but encryption not available")
            return encrypted_data  # Return as-is if encryption not available
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None
    
    def encrypt_dict(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Encrypt sensitive fields in a dictionary."""
        
        if not self._fernet:
            return data
        
        # Fields that should be encrypted
        sensitive_fields = ['email', 'phone', 'address', 'notes', 'personal_info']
        
        encrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in encrypted_data and isinstance(encrypted_data[field], str):
                encrypted_value = self.encrypt(encrypted_data[field])
                if encrypted_value:
                    encrypted_data[field] = encrypted_value
                    encrypted_data[f'{field}_encrypted'] = True
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Decrypt sensitive fields in a dictionary."""
        
        if not self._fernet:
            return data
        
        decrypted_data = data.copy()
        
        # Find encrypted fields
        encrypted_fields = [key for key in data.keys() if key.endswith('_encrypted') and data[key]]
        
        for encrypted_field in encrypted_fields:
            # Get the actual field name
            field_name = encrypted_field[:-10]  # Remove '_encrypted' suffix
            
            if field_name in decrypted_data:
                decrypted_value = self.decrypt(decrypted_data[field_name])
                if decrypted_value:
                    decrypted_data[field_name] = decrypted_value
                
                # Remove the encryption flag
                del decrypted_data[encrypted_field]
        
        return decrypted_data
    
    def hash_pii(self, data: str) -> str:
        """Create a one-way hash of PII for indexing purposes."""
        
        # Add a salt to prevent rainbow table attacks
        salt = os.getenv('STYLESYNC_HASH_SALT', 'default_salt_change_in_production')
        salted_data = f"{salt}:{data}"
        
        # Use SHA-256 for hashing
        hash_object = hashlib.sha256(salted_data.encode('utf-8'))
        return hash_object.hexdigest()
    
    def generate_key(self) -> str:
        """Generate a new Fernet encryption key."""
        key = Fernet.generate_key()
        return key.decode('utf-8')
    
    def encrypt_user_preferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt user preference data if needed."""
        
        # For now, user preferences are not considered sensitive enough to encrypt
        # But we hash any PII if present
        
        encrypted_prefs = preferences.copy()
        
        # Hash any potential PII
        if 'user_notes' in encrypted_prefs:
            encrypted_prefs['user_notes'] = self.hash_pii(encrypted_prefs['user_notes'])
        
        return encrypted_prefs
    
    def secure_delete_key(self):
        """Securely delete the encryption key from memory."""
        if self._fernet:
            # Python doesn't have secure memory clearing, but we can try
            self._fernet = None
            logger.info("Encryption key cleared from memory")


# Global encryption service instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get global encryption service instance."""
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    
    return _encryption_service


# Utility functions
def encrypt_if_enabled(data: str) -> str:
    """Encrypt data if encryption is enabled, otherwise return as-is."""
    service = get_encryption_service()
    if service.is_encryption_enabled():
        encrypted = service.encrypt(data)
        return encrypted if encrypted is not None else data
    return data


def decrypt_if_encrypted(data: str) -> str:
    """Decrypt data if it appears to be encrypted, otherwise return as-is."""
    service = get_encryption_service()
    if service.is_encryption_enabled() and len(data) > 50:  # Encrypted data is longer
        decrypted = service.decrypt(data)
        return decrypted if decrypted is not None else data
    return data
