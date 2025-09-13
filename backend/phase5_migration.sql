-- StyleSync Phase 5 Database Migration
-- Creates all necessary tables for personalization, feedback, and experimentation

-- Create custom types for enums
CREATE TYPE saturation_comfort AS ENUM ('low', 'medium', 'high');
CREATE TYPE lightness_comfort AS ENUM ('dark', 'mid', 'light'); 
CREATE TYPE season_bias AS ENUM ('all', 'spring_summer', 'autumn_winter');
CREATE TYPE experiment_status AS ENUM ('draft', 'active', 'paused', 'completed');

-- Users table (basic user tracking)
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    opt_out_personalization BOOLEAN DEFAULT FALSE,
    opt_out_experiments BOOLEAN DEFAULT FALSE
);

-- User preferences (explicit settings)
CREATE TABLE IF NOT EXISTS preferences (
    user_id VARCHAR(255) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    avoid_hues TEXT[] DEFAULT '{}', -- Array of hue names like ["green", "purple"]
    prefer_neutrals BOOLEAN DEFAULT FALSE,
    saturation_comfort saturation_comfort DEFAULT 'medium',
    lightness_comfort lightness_comfort DEFAULT 'mid',
    season_bias season_bias DEFAULT 'all',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Derived user features (computed from events)
CREATE TABLE IF NOT EXISTS features (
    user_id VARCHAR(255) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    hue_bias_json JSONB DEFAULT '{}', -- Map of hue bins (0-330 by 30s) to weights -1.0 to +1.0
    neutral_affinity FLOAT DEFAULT 0.5 CHECK (neutral_affinity >= 0 AND neutral_affinity <= 1),
    saturation_cap_adjust FLOAT DEFAULT 0.0 CHECK (saturation_cap_adjust >= -0.1 AND saturation_cap_adjust <= 0.1),
    lightness_bias FLOAT DEFAULT 0.0 CHECK (lightness_bias >= -0.1 AND lightness_bias <= 0.1),
    event_count INTEGER DEFAULT 0, -- Number of events used to compute features
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Advice sessions (track each advice request for analytics)
CREATE TABLE IF NOT EXISTS advice_sessions (
    advice_id VARCHAR(255) PRIMARY KEY,
    request_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE SET NULL,
    base_hex VARCHAR(7) NOT NULL, -- Base color from extraction
    policy_version VARCHAR(50) NOT NULL,
    experiment_name VARCHAR(100),
    experiment_arm VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    timings_json JSONB, -- Phase timings and cache hits
    from_cache BOOLEAN DEFAULT FALSE,
    personalized BOOLEAN DEFAULT FALSE
);

-- Suggestions generated for each advice session
CREATE TABLE IF NOT EXISTS suggestions (
    advice_id VARCHAR(255) REFERENCES advice_sessions(advice_id) ON DELETE CASCADE,
    rank INTEGER NOT NULL, -- Order in response (0-based)
    category VARCHAR(50) NOT NULL, -- complementary, analogous, triadic, neutrals
    hex VARCHAR(7) NOT NULL,
    hls_json JSONB NOT NULL, -- {h, l, s} values
    rationale_json JSONB, -- Reasoning for this suggestion
    is_personalized BOOLEAN DEFAULT FALSE, -- Whether this was reranked
    PRIMARY KEY (advice_id, rank)
);

-- Events (user interactions and feedback)
CREATE TABLE IF NOT EXISTS events (
    event_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    advice_id VARCHAR(255) REFERENCES advice_sessions(advice_id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'advice_viewed', 'suggestion_clicked', 'suggestion_applied', 
        'suggestion_liked', 'suggestion_disliked', 'advice_dismissed',
        'advice_rejected', 'flag_incorrect'
    )),
    category VARCHAR(50), -- Which suggestion category was interacted with
    suggestion_hex VARCHAR(7), -- Which specific color was interacted with
    base_hex VARCHAR(7) NOT NULL, -- Base color for context
    intent VARCHAR(50) NOT NULL, -- classic, bold, subtle, monochromatic
    season VARCHAR(50) NOT NULL, -- all, spring, summer, autumn, winter
    role_target VARCHAR(50) NOT NULL, -- top, bottom, outerwear, etc.
    timestamp_ms BIGINT NOT NULL, -- Client timestamp in milliseconds
    client VARCHAR(50) NOT NULL, -- web, ios, android
    latency_ms INTEGER, -- Request latency if available
    metadata_json JSONB DEFAULT '{}' -- Additional event-specific data
);

-- Experiments configuration
CREATE TABLE IF NOT EXISTS experiments (
    name VARCHAR(100) PRIMARY KEY,
    start_ts TIMESTAMP WITH TIME ZONE NOT NULL,
    end_ts TIMESTAMP WITH TIME ZONE,
    arms_json JSONB NOT NULL, -- Array of arm names
    allocation_json JSONB NOT NULL, -- Map of arm to percentage allocation
    status experiment_status DEFAULT 'draft',
    policy_variant_json JSONB DEFAULT '{}', -- Policy overrides per arm
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User experiment assignments (deterministic)
CREATE TABLE IF NOT EXISTS assignments (
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    experiment_name VARCHAR(100) NOT NULL REFERENCES experiments(name) ON DELETE CASCADE,
    arm VARCHAR(50) NOT NULL,
    assignment_token VARCHAR(255) NOT NULL, -- Unique token for this assignment
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, experiment_name)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_advice_sessions_user_created ON advice_sessions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_advice_sessions_experiment ON advice_sessions(experiment_name, experiment_arm);
CREATE INDEX IF NOT EXISTS idx_events_user_timestamp ON events(user_id, timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_events_advice_id ON events(advice_id);
CREATE INDEX IF NOT EXISTS idx_events_type_timestamp ON events(event_type, timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_assignments_user ON assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_assignments_experiment ON assignments(experiment_name);

-- Add retention policy function (for automatic cleanup)
CREATE OR REPLACE FUNCTION cleanup_old_events() RETURNS void AS $$
DECLARE
    retention_days INTEGER := 90; -- Default 90 day retention
BEGIN
    -- Delete events older than retention period
    DELETE FROM events 
    WHERE timestamp_ms < EXTRACT(EPOCH FROM NOW() - INTERVAL '90 days') * 1000;
    
    -- Clean up orphaned advice sessions (older than 30 days with no events)
    DELETE FROM advice_sessions 
    WHERE created_at < NOW() - INTERVAL '30 days'
    AND advice_id NOT IN (SELECT DISTINCT advice_id FROM events WHERE advice_id IS NOT NULL);
    
    RAISE NOTICE 'Cleaned up old events and orphaned sessions';
END;
$$ LANGUAGE plpgsql;

-- Create triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_preferences_updated_at BEFORE UPDATE ON preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_features_updated_at BEFORE UPDATE ON features
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_experiments_updated_at BEFORE UPDATE ON experiments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger to update user last_seen_at on any activity
CREATE OR REPLACE FUNCTION update_user_last_seen()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE users SET last_seen_at = NOW() WHERE user_id = NEW.user_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_last_seen_on_event AFTER INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION update_user_last_seen();

CREATE TRIGGER update_user_last_seen_on_advice AFTER INSERT ON advice_sessions
    FOR EACH ROW WHEN (NEW.user_id IS NOT NULL) EXECUTE FUNCTION update_user_last_seen();

-- Insert sample experiment for testing
INSERT INTO experiments (name, start_ts, arms_json, allocation_json, status, policy_variant_json) 
VALUES (
    'saturation_caps_test',
    NOW(),
    '["control", "variant"]',
    '{"control": 50, "variant": 50}',
    'active',
    '{
        "control": {},
        "variant": {
            "phase3_saturation_caps": {
                "top": 0.75,
                "bottom": 0.65
            }
        }
    }'
) ON CONFLICT (name) DO NOTHING;

-- Grant necessary permissions (adjust for your user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

COMMIT;
