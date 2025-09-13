"""
Phase 5 Configuration Management
Environment-specific settings, feature flags, and operational parameters.
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


class Environment(Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str
    port: int
    database: str
    username: str
    password: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    ssl_mode: str = "require"
    
    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return (
            f"postgresql://{self.username}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"
        )


@dataclass 
class RedisConfig:
    """Redis cache configuration."""
    host: str
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    max_connections: int = 50
    
    @property
    def connection_string(self) -> str:
        """Generate Redis connection string."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class SecurityConfig:
    """Security and authentication settings."""
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    encryption_key: Optional[str] = None
    bcrypt_rounds: int = 12
    
    # Rate limiting configuration
    rate_limit_profile_per_minute: int = 60
    rate_limit_events_per_minute: int = 1000
    rate_limit_analytics_per_minute: int = 100
    
    # Input validation
    max_colors_per_event: int = 10
    max_events_per_batch: int = 100
    max_preference_array_length: int = 20
    
    # Audit logging
    audit_log_retention_days: int = 90
    enable_pii_encryption: bool = False


@dataclass
class PersonalizationConfig:
    """Phase 5 personalization feature settings."""
    
    # Feature computation
    feature_time_decay_days: float = 30.0
    min_events_for_features: int = 5
    feature_computation_batch_size: int = 100
    
    # Color processing
    color_similarity_threshold: float = 0.7
    hue_bias_learning_rate: float = 0.1
    saturation_adjustment_range: float = 0.5
    lightness_adjustment_range: float = 0.5
    
    # Ranking
    base_score_weight: float = 0.7
    personalization_weight: float = 0.3
    freshness_decay_hours: float = 24.0
    max_suggestions_per_request: int = 50
    
    # Experiments
    default_experiment_split: float = 0.5
    experiment_assignment_salt: str = "what2wear_experiments"
    min_experiment_duration_days: int = 7
    
    # Performance
    suggestion_timeout_ms: int = 500
    feature_cache_ttl_hours: int = 6
    ranking_cache_ttl_minutes: int = 15


@dataclass
class ExperimentFlags:
    """A/B experiment feature flags."""
    
    # Active experiments
    enable_advanced_color_matching: bool = True
    enable_neural_ranking: bool = False
    enable_contextual_features: bool = True
    enable_seasonal_adjustments: bool = False
    
    # Experiment parameters
    advanced_color_matching_split: float = 0.5
    neural_ranking_split: float = 0.1
    contextual_features_split: float = 0.8
    seasonal_adjustments_split: float = 0.3
    
    # Performance experiments
    enable_aggressive_caching: bool = False
    enable_batch_processing: bool = True
    enable_async_features: bool = True


@dataclass
class MonitoringConfig:
    """Monitoring and observability settings."""
    
    # Logging
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "json"
    enable_sql_logging: bool = False
    enable_request_logging: bool = True
    
    # Metrics
    enable_prometheus_metrics: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    
    # Health checks
    health_check_timeout_seconds: int = 5
    database_health_check_query: str = "SELECT 1"
    redis_health_check_timeout_seconds: int = 2
    
    # Performance monitoring
    slow_query_threshold_ms: int = 1000
    slow_request_threshold_ms: int = 2000
    memory_alert_threshold_mb: int = 1024


@dataclass
class Phase5Config:
    """Complete Phase 5 configuration."""
    
    environment: Environment
    database: DatabaseConfig
    redis: RedisConfig
    security: SecurityConfig
    personalization: PersonalizationConfig
    experiments: ExperimentFlags
    monitoring: MonitoringConfig
    
    # API configuration
    api_title: str = "What2Wear Phase 5 Personalization API"
    api_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    
    # External service URLs
    base_api_url: str = "http://localhost:8000"
    storage_service_url: str = "http://localhost:8001"
    
    @classmethod
    def from_environment(cls) -> 'Phase5Config':
        """Load configuration from environment variables."""
        
        env = Environment(os.getenv('ENVIRONMENT', 'development'))
        
        # Database configuration
        database = DatabaseConfig(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', '5432')),
            database=os.getenv('DATABASE_NAME', 'what2wear'),
            username=os.getenv('DATABASE_USERNAME', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD', 'password'),
            pool_size=int(os.getenv('DATABASE_POOL_SIZE', '10')),
            ssl_mode=os.getenv('DATABASE_SSL_MODE', 'require' if env == Environment.PRODUCTION else 'prefer')
        )
        
        # Redis configuration
        redis = RedisConfig(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            db=int(os.getenv('REDIS_DB', '0')),
            password=os.getenv('REDIS_PASSWORD'),
            max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', '50'))
        )
        
        # Security configuration
        security = SecurityConfig(
            jwt_secret_key=os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production'),
            encryption_key=os.getenv('ENCRYPTION_KEY'),
            enable_pii_encryption=os.getenv('ENABLE_PII_ENCRYPTION', 'false').lower() == 'true',
            rate_limit_profile_per_minute=int(os.getenv('RATE_LIMIT_PROFILE', '60')),
            rate_limit_events_per_minute=int(os.getenv('RATE_LIMIT_EVENTS', '1000')),
            audit_log_retention_days=int(os.getenv('AUDIT_LOG_RETENTION_DAYS', '90'))
        )
        
        # Personalization configuration
        personalization = PersonalizationConfig(
            feature_time_decay_days=float(os.getenv('FEATURE_TIME_DECAY_DAYS', '30.0')),
            min_events_for_features=int(os.getenv('MIN_EVENTS_FOR_FEATURES', '5')),
            suggestion_timeout_ms=int(os.getenv('SUGGESTION_TIMEOUT_MS', '500')),
            feature_cache_ttl_hours=int(os.getenv('FEATURE_CACHE_TTL_HOURS', '6'))
        )
        
        # Experiment flags
        experiments = ExperimentFlags(
            enable_advanced_color_matching=os.getenv('ENABLE_ADVANCED_COLOR_MATCHING', 'true').lower() == 'true',
            enable_neural_ranking=os.getenv('ENABLE_NEURAL_RANKING', 'false').lower() == 'true',
            enable_contextual_features=os.getenv('ENABLE_CONTEXTUAL_FEATURES', 'true').lower() == 'true',
            advanced_color_matching_split=float(os.getenv('ADVANCED_COLOR_MATCHING_SPLIT', '0.5')),
            neural_ranking_split=float(os.getenv('NEURAL_RANKING_SPLIT', '0.1'))
        )
        
        # Monitoring configuration
        monitoring = MonitoringConfig(
            log_level=LogLevel(os.getenv('LOG_LEVEL', 'INFO')),
            enable_prometheus_metrics=os.getenv('ENABLE_PROMETHEUS_METRICS', 'true').lower() == 'true',
            enable_sql_logging=os.getenv('ENABLE_SQL_LOGGING', 'false').lower() == 'true',
            slow_query_threshold_ms=int(os.getenv('SLOW_QUERY_THRESHOLD_MS', '1000'))
        )
        
        return cls(
            environment=env,
            database=database,
            redis=redis,
            security=security,
            personalization=personalization,
            experiments=experiments,
            monitoring=monitoring,
            api_host=os.getenv('API_HOST', '0.0.0.0'),
            api_port=int(os.getenv('API_PORT', '8000')),
            api_workers=int(os.getenv('API_WORKERS', '4')),
            base_api_url=os.getenv('BASE_API_URL', 'http://localhost:8000'),
            storage_service_url=os.getenv('STORAGE_SERVICE_URL', 'http://localhost:8001')
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'Phase5Config':
        """Load configuration from JSON file."""
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Convert nested dicts to dataclass instances
        database_data = config_data.pop('database')
        redis_data = config_data.pop('redis')
        security_data = config_data.pop('security')
        personalization_data = config_data.pop('personalization')
        experiments_data = config_data.pop('experiments')
        monitoring_data = config_data.pop('monitoring')
        
        return cls(
            database=DatabaseConfig(**database_data),
            redis=RedisConfig(**redis_data),
            security=SecurityConfig(**security_data),
            personalization=PersonalizationConfig(**personalization_data),
            experiments=ExperimentFlags(**experiments_data),
            monitoring=MonitoringConfig(**monitoring_data),
            **config_data
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    def to_file(self, config_path: str) -> None:
        """Save configuration to JSON file."""
        
        with open(config_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues."""
        
        issues = []
        
        # Security validation
        if self.environment == Environment.PRODUCTION:
            if self.security.jwt_secret_key == 'dev-secret-key-change-in-production':
                issues.append("Production environment requires a secure JWT secret key")
            
            if not self.security.encryption_key and self.security.enable_pii_encryption:
                issues.append("PII encryption enabled but no encryption key provided")
            
            if self.database.ssl_mode != 'require':
                issues.append("Production environment should require SSL for database connections")
        
        # Personalization validation
        if self.personalization.feature_time_decay_days <= 0:
            issues.append("Feature time decay days must be positive")
        
        if self.personalization.min_events_for_features < 1:
            issues.append("Minimum events for features must be at least 1")
        
        if not (0.0 <= self.personalization.base_score_weight <= 1.0):
            issues.append("Base score weight must be between 0.0 and 1.0")
        
        if not (0.0 <= self.personalization.personalization_weight <= 1.0):
            issues.append("Personalization weight must be between 0.0 and 1.0")
        
        # Experiment validation
        for attr_name in dir(self.experiments):
            if attr_name.endswith('_split'):
                split_value = getattr(self.experiments, attr_name)
                if not (0.0 <= split_value <= 1.0):
                    issues.append(f"Experiment split {attr_name} must be between 0.0 and 1.0")
        
        # Performance validation
        if self.personalization.suggestion_timeout_ms < 100:
            issues.append("Suggestion timeout should be at least 100ms")
        
        if self.personalization.max_suggestions_per_request > 200:
            issues.append("Maximum suggestions per request should not exceed 200")
        
        return issues


# Environment-specific presets
DEVELOPMENT_CONFIG = {
    "environment": "development",
    "database": {
        "host": "localhost",
        "port": 5432,
        "database": "what2wear_dev",
        "username": "postgres",
        "password": "password",
        "ssl_mode": "prefer"
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0
    },
    "security": {
        "jwt_secret_key": "dev-secret-key-change-in-production",
        "enable_pii_encryption": False,
        "audit_log_retention_days": 30
    },
    "monitoring": {
        "log_level": "DEBUG",
        "enable_sql_logging": True,
        "enable_prometheus_metrics": False
    }
}

STAGING_CONFIG = {
    "environment": "staging",
    "database": {
        "ssl_mode": "require"
    },
    "security": {
        "enable_pii_encryption": True,
        "audit_log_retention_days": 60
    },
    "monitoring": {
        "log_level": "INFO",
        "enable_sql_logging": False,
        "enable_prometheus_metrics": True
    }
}

PRODUCTION_CONFIG = {
    "environment": "production",
    "database": {
        "pool_size": 20,
        "max_overflow": 40,
        "ssl_mode": "require"
    },
    "security": {
        "enable_pii_encryption": True,
        "bcrypt_rounds": 15,
        "audit_log_retention_days": 365
    },
    "personalization": {
        "suggestion_timeout_ms": 300,
        "feature_cache_ttl_hours": 12
    },
    "monitoring": {
        "log_level": "WARNING",
        "enable_sql_logging": False,
        "enable_prometheus_metrics": True,
        "slow_query_threshold_ms": 500
    }
}


def get_config() -> Phase5Config:
    """Get configuration for current environment."""
    
    # Try to load from environment variables first
    config = Phase5Config.from_environment()
    
    # Validate configuration
    issues = config.validate()
    if issues:
        print(f"Configuration issues found: {issues}")
        if config.environment == Environment.PRODUCTION:
            raise ValueError(f"Production configuration invalid: {issues}")
    
    return config


def create_sample_configs():
    """Create sample configuration files for each environment."""
    
    environments = {
        'development': DEVELOPMENT_CONFIG,
        'staging': STAGING_CONFIG,
        'production': PRODUCTION_CONFIG
    }
    
    for env_name, env_config in environments.items():
        # Create base config and merge environment-specific overrides
        base_config = Phase5Config.from_environment()
        config_dict = base_config.to_dict()
        
        def merge_config(base: dict, override: dict):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_config(base[key], value)
                else:
                    base[key] = value
        
        merge_config(config_dict, env_config)
        
        # Save to file
        filename = f"config_{env_name}.json"
        with open(filename, 'w') as f:
            json.dump(config_dict, f, indent=2, default=str)
        
        print(f"Created {filename}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create-samples":
        create_sample_configs()
    else:
        # Print current configuration
        config = get_config()
        print(f"Environment: {config.environment.value}")
        print(f"Database: {config.database.host}:{config.database.port}")
        print(f"Redis: {config.redis.host}:{config.redis.port}")
        print(f"API: {config.api_host}:{config.api_port}")
        
        if config.validate():
            print(f"Configuration issues: {config.validate()}")
        else:
            print("Configuration is valid")
